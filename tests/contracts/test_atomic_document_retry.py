import os

import pytest

from kg_mnp.contracts.document_io import atomic_write_bytes


def test_transient_windows_sharing_violation_retries_only_owned_replace(tmp_path,monkeypatch):
    destination=tmp_path/"record.json";real=os.replace;attempts=[]
    def replace(source,target):
        attempts.append(target)
        if len(attempts)==1:
            error=PermissionError("sharing violation");error.winerror=32;raise error
        return real(source,target)
    monkeypatch.setattr(os,"replace",replace)
    atomic_write_bytes(destination,b'{"committed":true}')
    assert destination.read_bytes()==b'{"committed":true}' and len(attempts)==2


def test_persistent_permission_denial_never_reports_commit(tmp_path,monkeypatch):
    destination=tmp_path/"record.json";destination.write_bytes(b'original')
    def denied(*args):
        error=PermissionError("denied");error.winerror=5;raise error
    monkeypatch.setattr(os,"replace",denied)
    with pytest.raises(PermissionError):atomic_write_bytes(destination,b'new')
    assert destination.read_bytes()==b'original'
    assert not list(tmp_path.glob('*.tmp'))
