from __future__ import annotations

from fastapi.testclient import TestClient

from kg_mnp_demo.modeling.dependencies import ROOT
from kg_mnp_demo.workbench.binding import WorkbenchBinding
from kg_mnp_demo.workbench.runtime import create_workbench_app

from ._helpers import ENTITY, FakeRelay, write_phase01_artifact


ATTACKS = (
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "&#x6a;avascript:alert(1)",
    "%3Cscript%3Ealert(1)%3C/script%3E",
    "\"</div><script>alert(1)</script>",
    "urn:datatype:<script>alert(1)</script>",
    "en-<img-src-x>",
    "urn:source:<svg-onload-alert>",
)


def test_frontend_uses_only_text_dom_rendering_and_no_persistent_authority() -> None:
    javascript = (ROOT / "web/workbench/assets/app.js").read_text(encoding="utf-8")
    forbidden = (
        "inner" + "HTML",
        "dangerouslySet" + "InnerHTML",
        "eval" + "(",
        "new" + " Function",
        "document" + ".write",
        "local" + "Storage",
        "indexed" + "DB",
        "service" + "Worker",
    )
    assert "textContent" in javascript
    assert all(marker not in javascript for marker in forbidden)


def test_malicious_rdf_text_remains_json_data_for_text_renderer(tmp_path) -> None:
    for attack in ATTACKS:
        artifact = write_phase01_artifact(tmp_path / attack.encode().hex()[:20])
        binding = WorkbenchBinding.load(artifact)
        app = create_workbench_app(
            binding=binding,
            relay=FakeRelay(binding, payload=attack),
        )
        with TestClient(app, raise_server_exceptions=False) as http:
            response = http.get(
                "/workbench/api/view/entity",
                params={"iri": ENTITY},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/json")
            term = response.json()["rows"][0]["bindings"][-1]["term"]
            assert term["lexical_form"] == attack
