"""Explicit preparation of the one digest-pinned reasoner, never runtime download."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
EXPECTED='91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d'
URL='https://github.com/ontodev/robot/releases/download/v1.9.7/robot.jar'


def main():
    destination=ROOT/'third_party/downloads/robot-1.9.7.jar'
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest()!=EXPECTED:
            raise SystemExit('Existing reasoner digest mismatch; no automatic overwrite')
    else:
        with urlopen(URL,timeout=60) as response:
            content=response.read(100*1024*1024)
        if hashlib.sha256(content).hexdigest()!=EXPECTED:
            raise SystemExit('Downloaded reasoner digest mismatch')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(content)
    print('Pinned ROBOT 1.9.7 verified')


if __name__=='__main__':
    main()
