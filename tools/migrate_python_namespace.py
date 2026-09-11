"""Mechanical source-only namespace migration; never rewrite stored identities."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Import syntax and source/build paths only. No RDF/JSON/YAML assets or
    # historical reports are part of this rewrite.
    targets = [*list((ROOT / "src" / "zhigou_toolchain").rglob("*.py")),
               *list((ROOT / "tools").glob("*.py")), ROOT / "setup.py"]
    for path in targets:
        if path == Path(__file__).resolve():
            continue
        old = path.read_text(encoding="utf-8")
        new = re.sub(r"\bfrom kg_mnp(?=\.| import)", "from zhigou_toolchain", old)
        new = re.sub(r"\bimport kg_mnp(?=\.|\s|$)", "import zhigou_toolchain", new)
        # import statements with aliases retain their binding; existing plugin
        # dotted entrypoints deliberately continue through the legacy alias.
        new = new.replace('src/kg_mnp', 'src/zhigou_toolchain')
        new = new.replace('"src" / "kg_mnp"', '"src" / "zhigou_toolchain"')
        new = new.replace('resources.files("kg_mnp', 'resources.files("zhigou_toolchain')
        new = new.replace('__import__("kg_mnp.', '__import__("zhigou_toolchain.')
        new = re.sub(r'os\.(?:environ\.get|getenv)\((["\x27])KG_MNP_', r'get_setting(\1', new)
        if new != old and "get_setting(" in new and "from zhigou_toolchain.environment import get_setting" not in new:
            anchor = "from __future__ import annotations\n"
            if anchor in new:
                new = new.replace(anchor, anchor + "\nfrom zhigou_toolchain.environment import get_setting\n", 1)
            else:
                # Every affected source has either future annotations or an
                # import os at top level; preserve the module docstring.
                new = new.replace("import os\n", "import os\nfrom zhigou_toolchain.environment import get_setting\n", 1)
        if path.name == "setup.py":
            new = new.replace('"kg_mnp"', '"zhigou_toolchain"')
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
    # These checks inspect today's filesystem, not immutable git objects.
    # Historical git-show fixtures and repository_history.py stay unchanged.
    live_checks = ["tests/activation/test_phase05_public_surface_freeze.py", "tests/application/test_application_boundaries_phase01.py",
        "tests/contracts/test_registry_and_artifacts.py", "tests/governance/test_stage_boundaries.py", "tests/modeling/test_contract_registry.py",
        "tests/graphdb/test_stage07_boundaries.py", "tests/refactor/test_product_boundaries.py", "tests/webvowl/test_stage08_boundaries.py",
        "tests/modeling/test_stage04_boundaries.py", "tests/review/test_stage05_boundaries.py", "scripts/check_schema_identifiers.py", "scripts/check_ontology_release.py"]
    for name in live_checks:
        path = ROOT / name
        old = path.read_text(encoding="utf-8")
        new = old.replace("src/kg_mnp", "src/zhigou_toolchain").replace('"src" / "kg_mnp"', '"src" / "zhigou_toolchain"')
        if "phase05_public_surface_freeze" in name:
            new = new.replace('"kg_mnp.activation"', '"zhigou_toolchain.activation"')
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
