import socket

import pytest

from kg_mnp.integrations.targets import validate_endpoint


def test_local_graphdb_exception_does_not_allow_arbitrary_hosts(monkeypatch):
    def forbidden_resolution(*args,**kwargs):
        raise AssertionError('unapproved host must be rejected before resolution')
    monkeypatch.setattr(socket,'getaddrinfo',forbidden_resolution)
    with pytest.raises(ValueError):
        validate_endpoint('http://unapproved.invalid:7200',allow_local_graphdb=True)


def test_local_name_cannot_resolve_to_metadata_address(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('169.254.169.254',7200))])
    with pytest.raises(ValueError):
        validate_endpoint('http://localhost:7200',allow_local_graphdb=True)


def test_explicit_loopback_target_remains_available():
    assert validate_endpoint('http://127.0.0.1:7200',allow_local_graphdb=True)==('http','127.0.0.1',7200)
