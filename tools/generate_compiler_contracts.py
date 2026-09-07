"""Generate current compiler-version contracts, preserving every v1.0 byte."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import yaml

from kg_mnp.contracts.canonical import semantic_hash, stable_urn

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=ROOT/'src/kg_mnp/contracts'


def outputs():
    files={}
    for name in ('policy','snapshot'):
        old=CONTRACTS/f'schemas/compilation/semantic_compiler_{name}.schema.json'
        value=json.loads(old.read_bytes())
        value=copy.deepcopy(value)
        value['$id']=value['$id'].removesuffix('/1.0')+'/1.1'
        value['title']=value['title'].replace('1.0','1.1')
        value['properties']['schema_version']={'const':'1.1.0'}
        value['properties']['compiler_version']={'const':'0.5.1'}
        if name=='policy':
            value['properties']['policy_version']={'const':'1.1.0'}
        else:
            value['properties']['toolchain_version']={'type':'string','minLength':1,'maxLength':128}
        files[CONTRACTS/f'schemas/compilation/semantic_compiler_{name}_v1_1.schema.json']=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    policy_dir=ROOT/'src/kg_mnp/semantic_kernel/resources'
    policy=yaml.safe_load((policy_dir/'toolchain-compiler-policy-1.0.0.yaml').read_bytes())
    policy.update(schema_version='1.1.0',policy_version='1.1.0',compiler_version='0.5.1')
    policy['content_digest']=semantic_hash({k:v for k,v in policy.items() if k not in {'policy_id','content_digest'}})
    policy['policy_id']=stable_urn('semantic-compiler-policy',{'content_digest':policy['content_digest']})
    files[policy_dir/'toolchain-compiler-policy-1.1.0.yaml']=yaml.safe_dump(policy,allow_unicode=True,sort_keys=False).encode()
    return files


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for path,content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_bytes()!=content:
                raise SystemExit(f'Generated compiler resource is stale: {path.relative_to(ROOT)}')
        else:
            path.write_bytes(content)
        print(path.relative_to(ROOT).as_posix(),hashlib.sha256(content).hexdigest())


if __name__=='__main__':
    main()
