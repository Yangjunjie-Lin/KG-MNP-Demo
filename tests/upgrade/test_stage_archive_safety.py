from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from zhigou_toolchain.modeling.delivery.exchange_io import read_archive, read_bounded


@pytest.mark.parametrize("name", ["../escape", "/root", "C:/drive", "a\\b", "file:stream", "CON", "path./x"])
def test_unsafe_zip_paths_rejected_without_extraction(name):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("axb" if name == "a\\b" else name, b"not executed")
    raw = output.getvalue().replace(b"axb", b"a\\b") if name == "a\\b" else output.getvalue()
    with pytest.raises(ValueError):
        read_archive(raw)


def test_duplicate_case_link_and_zip_expansion_are_rejected():
    for kind in ("duplicate", "link", "expansion", "file-directory"):
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if kind == "link":
                info = zipfile.ZipInfo("link")
                info.external_attr = 0o120777 << 16
                archive.writestr(info, b"../../private")
            elif kind == "expansion":
                archive.writestr("bomb", b"x" * 5_000_000)
            else:
                archive.writestr("item", b"a")
                archive.writestr("ITEM" if kind == "duplicate" else "item/child", b"b")
        with pytest.raises(ValueError):
            read_archive(output.getvalue())


def test_scripts_are_returned_as_bytes_never_executed():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("script.py", b'raise RuntimeError("MUST_NOT_RUN")')
    assert read_archive(output.getvalue())["script.py"].startswith(b"raise")


def test_small_file_capture_does_not_allocate_the_resource_cap(tmp_path, monkeypatch):
    from pathlib import Path
    target = tmp_path / "tiny"
    target.write_bytes(b"abc")
    original = Path.open
    requested = []
    class ObservedReader:
        def __enter__(self):
            self.stream = original(target, "rb")
            return self
        def __exit__(self, *args):
            self.stream.close()
        def read(self, count):
            requested.append(count)
            return self.stream.read(count)
    monkeypatch.setattr(Path, "open", lambda path, *args, **kwargs: ObservedReader() if path == target else original(path, *args, **kwargs))
    assert read_bounded(target, limit=256_000_000) == b"abc"
    assert requested == [4]


def test_file_growth_during_capture_is_rejected(tmp_path, monkeypatch):
    from pathlib import Path
    target = tmp_path / "changing"
    target.write_bytes(b"abc")
    original = Path.open
    def opened(path, *args, **kwargs):
        if path == target:
            with original(target, "ab") as stream:
                stream.write(b"d")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(ValueError, match="FILE_CHANGED"):
        read_bounded(target)


def test_full_regression_raw_log_cannot_replace_wrapper_receipt(tmp_path):
    from tools.verify_stage_handoff import add_full_receipts
    evidence = {"relevant-test-receipts/full-backend.log": b"wrapper-command-and-exit-code"}
    for name in ("backend.xml", "backend.log", "reports.json", "verification.json"):
        (tmp_path / name).write_bytes(b"raw-" + name.encode())
    add_full_receipts(evidence, tmp_path)
    assert evidence["relevant-test-receipts/full-backend.log"] == b"wrapper-command-and-exit-code"
    assert evidence["relevant-test-receipts/full-backend-raw/backend.log"] == b"raw-backend.log"
    with pytest.raises(ValueError, match="DUPLICATE_TEST_RECEIPT_PATH"):
        add_full_receipts(evidence, tmp_path)
