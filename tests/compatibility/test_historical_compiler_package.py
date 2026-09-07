import hashlib
import json
from pathlib import Path

from kg_mnp.semantic_kernel.packaging.archive import verify_kgop


def test_prior_compiler_package_bytes_and_identity_remain_verifiable():
    directory=Path(__file__).with_name('fixtures')
    expected=json.loads((directory/'compiler-0.5.0.json').read_bytes())
    archive=directory/'compiler-0.5.0.kgop'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected['archive_sha256']
    result=verify_kgop(archive)
    assert result['status']=='VALID'
    assert result['package_id']==expected['package_id']
