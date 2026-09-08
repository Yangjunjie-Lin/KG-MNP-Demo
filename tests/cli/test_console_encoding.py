"""Console transport must not corrupt Chinese identifiers or JSON contracts."""
import io
import json

import pytest

from kg_mnp.contracts import cli


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "utf-8"])
def test_current_json_emitter_preserves_unicode_on_real_encoded_stream(monkeypatch, encoding):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(cli.sys, "stdout", stream)
    cli.emit_json({"label": "资格判断 / 林业本体", "literal": "木"})
    stream.flush()
    assert json.loads(raw.getvalue().decode(encoding)) == {"label": "资格判断 / 林业本体", "literal": "木"}


def test_current_json_emitter_rejects_nonfinite_numbers():
    with pytest.raises(ValueError):
        cli.emit_json({"value": float("nan")})
