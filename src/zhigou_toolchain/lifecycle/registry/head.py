from pathlib import Path

from ._common import read


def read_head(root): return read(Path(root),"state/registry-head.json")
