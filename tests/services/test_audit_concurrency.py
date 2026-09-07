import json
from concurrent.futures import ThreadPoolExecutor

from kg_mnp.contracts.canonical import semantic_hash
from kg_mnp.services.audit import AuditLog


def test_concurrent_audit_appends_have_one_contiguous_chain(tmp_path):
    audit=AuditLog(tmp_path/"audit.jsonl")
    def append(i):return audit.append(principal_id="synthetic",operation_id="read",project_id="p",request_id=str(i),outcome="SUCCEEDED",details={})
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(append,range(80)))
    rows=[json.loads(line) for line in audit.path.read_text(encoding="utf8").splitlines()]
    previous=None
    for row in rows:
        assert row["previous_hash"]==previous
        assert row["content_hash"]==semantic_hash({k:v for k,v in row.items() if k!="content_hash"})
        previous=row["content_hash"]
    assert len(rows)==80
    assert audit.verify()["status"]=="VALID"
