"""Bundle the one generated Workbench build into the Python distribution."""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithWorkbench(build_py):
    def run(self):
        super().run()
        source = Path(__file__).parent / "workbench" / "dist"
        if not (source / "index.html").is_file():
            raise RuntimeError("Build Workbench first: cd workbench; npm ci; npm run build")
        shutil.copytree(source, Path(self.build_lib) / "kg_mnp" / "workbench_static", dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildWithWorkbench})
