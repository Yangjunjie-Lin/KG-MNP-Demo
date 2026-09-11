"""Probe only synthetic data; print status codes, never credentials or URLs."""
import json
import os
from pathlib import Path
from time import perf_counter

import httpx


def main():
    output = Path('runtime_reports/original-service-probe')
    output.mkdir(parents=True, exist_ok=True)
    requests = {
        'qwen': ('chat/completions', {'model': 'Qwen/Qwen2.5-7B-Instruct', 'messages': [{'role': 'user', 'content': 'Return JSON only: the object type SyntheticInspection as object_type.'}], 'max_tokens': 100, 'response_format': {'type': 'json_object'}}),
        'bge': ('embeddings', {'model': 'BAAI/bge-m3', 'input': ['tree inspection', 'employee payroll']}),
        'reranker': ('rerank', {'model': 'BAAI/bge-reranker-v2-m3', 'query': 'tree inspection', 'documents': ['Inspect a tree for damage.', 'An employee salary statement.'], 'top_n': 2}),
    }
    with httpx.Client(base_url='https://api.siliconflow.cn/v1/', headers={'Authorization': 'Bearer ' + os.environ['SILICONFLOW_API_KEY']}, timeout=90, follow_redirects=False, trust_env=False) as client:
        for name, (endpoint, payload) in requests.items():
            started = perf_counter()
            try:
                response = client.post(endpoint, json=payload)
                receipt = {'http_status': response.status_code, 'model': payload['model'], 'duration_seconds': perf_counter() - started}
                if response.is_success:
                    receipt['response'] = response.json()
                else:
                    try:
                        code = response.json().get('code')
                        receipt['provider_code'] = code if isinstance(code, int) else None
                    except ValueError:
                        pass
                (output / (name + '.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps({k: v for k, v in receipt.items() if k != 'response'}), flush=True)
            except httpx.HTTPError as exc:
                print(json.dumps({'model': name, 'error': type(exc).__name__}), flush=True)


if __name__ == '__main__':
    main()
