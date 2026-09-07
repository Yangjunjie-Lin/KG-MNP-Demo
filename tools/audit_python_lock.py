"""Query PyPI release advisory metadata for exact public dependency pins.

This is a network advisory check, not a proof that dependencies have no defects.
Only public package names and versions from the lock are sent to PyPI.
"""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen


def check(pin):
    name, version = pin
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urlopen(url, timeout=20) as response:
            body = response.read(4000000)
        value = json.loads(body)
        return {"name":name,"version":version,"source":url,"status":"CHECKED", "response_sha256":hashlib.sha256(body).hexdigest(),
                "vulnerabilities":value.get("vulnerabilities",[])}
    except (OSError, ValueError, KeyError) as exc:
        return {"name":name,"version":version,"source":url,"status":"UNVERIFIED","error_type":type(exc).__name__}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("lock",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    pins=[]
    for line in args.lock.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match=re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)",line)
        if not match:
            raise SystemExit("only exact public dependency pins are accepted")
        pins.append(match.groups())
    with ThreadPoolExecutor(max_workers=4) as workers:
        rows=list(workers.map(check,pins))
    report={"checked_at":datetime.now(UTC).isoformat(),"lock_sha256":hashlib.sha256(args.lock.read_bytes()).hexdigest(),"packages":rows,
            "limitations":"PyPI advisory metadata only; unpublished or unknown vulnerabilities are not excluded."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    affected=[{"name":row["name"],"version":row["version"],"advisories":[{"id":v["id"],"fixed_in":v.get("fixed_in",[])} for v in row.get("vulnerabilities",[])]}
              for row in rows if row.get("vulnerabilities")]
    print(json.dumps({"checked":sum(row["status"]=="CHECKED" for row in rows),"unverified":sum(row["status"]!="CHECKED" for row in rows),"affected":affected},indent=2))
    raise SystemExit(1 if affected or any(row["status"]!="CHECKED" for row in rows) else 0)


if __name__=="__main__":
    main()
