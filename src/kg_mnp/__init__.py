"""Deprecated import namespace; all submodules share the sole implementation."""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys

from zhigou_toolchain import __version__


class _LegacyLoader(importlib.abc.Loader):
    def __init__(self, target):
        self.target = target

    def create_module(self, spec):
        module = importlib.import_module(self.target)
        self.original_spec = module.__spec__
        return module

    def exec_module(self, module):
        module.__spec__ = self.original_spec


class _LegacyFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith("kg_mnp.") or fullname in {"kg_mnp.__main__", "kg_mnp.root_cli"}:
            return None
        name = "zhigou_toolchain" + fullname[len("kg_mnp"):]
        spec = importlib.util.find_spec(name)
        if spec is None:
            return None
        return importlib.util.spec_from_loader(fullname, _LegacyLoader(name), is_package=spec.submodule_search_locations is not None)


sys.meta_path.insert(0, _LegacyFinder())


def legacy_main():
    print("DEPRECATED: kg-mnp / kg_mnp now use zhigou-toolchain / zhigou_toolchain", file=sys.stderr)
    from zhigou_toolchain.root_cli import main
    return main()


__all__ = ["__version__", "legacy_main"]
