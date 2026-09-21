"""The user-confirmed simplified reference is evidence, not runtime model input."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from tools.verify_stage_handoff import attachment_reference
from zhigou_toolchain.modeling.delivery.evolution import EVENT_FIELDS
from zhigou_toolchain.modeling.delivery.exchange_io import (
    digest,
    read_archive,
    verify_rows,
)
from zhigou_toolchain.modeling.delivery.meeting_input import (
    generation_files,
    validate_input,
)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = ROOT / "docs/ontology/references"


def reference_files():
    identity = json.loads((REFERENCE_ROOT / "handoff-17.reference.json").read_bytes())
    raw = (REFERENCE_ROOT / identity["archive"]).read_bytes()
    assert digest(raw) == identity["sha256"] and len(raw) == identity["size_bytes"]
    contents = read_archive(raw)
    roots = {n.split("/")[0] for n in contents}
    assert len(roots) == 1
    prefix = roots.pop() + "/"
    return identity, raw, {n.removeprefix(prefix): v for n, v in contents.items()}


def test_user_confirmation_pins_real_bytes_without_rewriting_old_identity():
    identity, raw, files = reference_files()
    result = attachment_reference(raw)
    assert result["requested_attachment_status"] == "MATCH_USER_CONFIRMED_REFERENCE"
    assert result["reference_role"] == "SIMPLIFIED_HANDOFF_REFERENCE"
    assert result["reference_confirmation"] == "USER_CONFIRMED_ALIAS"
    assert identity["sha256"] != result["previous_prompt_archive_sha256"]
    assert result["previous_prompt_identity"] == "DIFFERENT_BYTES_NOT_REWRITTEN"
    index = json.loads(files["package_index.json"])
    assert index["package_kind"] == "HANDOFF_DOCUMENTATION" and not index["runtime_artifacts_included"]
    assert verify_rows(files, index["files"]) == {n.casefold() for n in files if n != "package_index.json"}


def test_name_or_embedded_claim_cannot_confirm_different_bytes():
    _, raw, _ = reference_files()
    result = attachment_reference(raw + b"same-name-but-different-bytes")
    assert result["requested_attachment_status"] == "DIFFERENT_UNCONFIRMED_REFERENCE"
    assert result["reference_id"] is None and result["reference_confirmation"] is None


def test_confirmed_reference_only_exposes_upstream_generation_allowlist():
    _, _, files = reference_files()
    upstream = {n.removeprefix("upstream/"): v for n, v in files.items() if n.startswith("upstream/")}
    parsed = validate_input(upstream)
    assert parsed["manifest"]["reference_domain_pack"]["repository_commit"] == "194e091d13cabba5833ff1d531f814858ea968ae"
    view = generation_files(upstream)
    assert set(view) == set(parsed["manifest"]["generation_allowlist"]) | {"manifest.json"}
    assert not any(n.startswith("acceptance_private/") or n.endswith((".zip", ".xlsx", ".html")) for n in view)


def test_reference_markdown_event_requirements_equal_the_actual_validator():
    _, _, files = reference_files()
    markdown = files["本体建模下游交接说明.md"].decode("utf-8")
    declared = {}
    for line in markdown.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] in EVENT_FIELDS:
            declared[cells[0]] = tuple(cells[1].split("、"))
    assert declared == EVENT_FIELDS
    for text in ("pass/fail", "corrected_answer", "violations", "batch_id / files", "未知 event 仅告警", "空批次"):
        assert text in markdown


def test_excel_and_html_keep_exactly_the_17_numbered_items():
    _, _, files = reference_files()
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(BytesIO(files["上下游交接清单.xlsx"])) as workbook:
        strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in row.findall(".//s:t", ns)) for row in root]
        numbers = []
        for name in sorted(n for n in workbook.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
            root = ElementTree.fromstring(workbook.read(name))
            for cell in root.findall(".//s:c", ns):
                if not re.fullmatch(r"A\d+", cell.get("r", "")):
                    continue
                value = cell.findtext("s:v", default="", namespaces=ns)
                text = strings[int(value)] if cell.get("t") == "s" else value if cell.get("t") == "str" else "".join(t.text or "" for t in cell.findall(".//s:t", ns))
                match = re.match(r"^(\d{2})\s+", text)
                if match:
                    numbers.append(match[1])
        assert numbers == [f"{i:02}" for i in range(1, 18)]
    html = files["index.html"].decode("utf-8")
    for number in numbers:
        assert re.search(r">\s*" + number + r"\s*<", html)
    assert '"Times New Roman","SimSun","宋体"' in html


def test_direct_verifier_entrypoint_can_resolve_its_packaging_helpers(tmp_path):
    # Reproduce direct-script sys.path without PYTHONPATH or a repository cwd.
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    environment["PYTHONUTF8"] = "1"
    code = "import runpy,sys; runpy.run_path(sys.argv[1],run_name='entrypoint_probe'); from tests.upgrade.stage_support import case_files; print(case_files.__module__)"
    result = subprocess.run([sys.executable, "-c", code, str(ROOT / "tools/verify_stage_handoff.py")], cwd=tmp_path,
                            env=environment, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert result.stdout.decode().strip() == "tests.upgrade.stage_support"
