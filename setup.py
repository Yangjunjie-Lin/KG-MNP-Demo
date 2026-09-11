"""Bundle the one generated Workbench build into the Python distribution."""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithWorkbench(build_py):
    def run(self):
        if getattr(self, "editable_mode", False):
            super().run()
            return
        # Only disposable output inside this source tree's build directory may
        # be replaced. Never recursively clear a custom/source Workspace path.
        allowed = (Path(__file__).parent / "build").resolve()
        for namespace in ("zhigou_toolchain", "kg_mnp"):
            package_output = (Path(self.build_lib) / namespace).absolute()
            if package_output.is_symlink() or not package_output.resolve().is_relative_to(allowed):
                raise RuntimeError("Package build output must stay inside the controlled build directory")
            if package_output.exists():
                shutil.rmtree(package_output)
        super().run()
        source = Path(__file__).parent / "workbench" / "dist"
        if not (source / "index.html").is_file() or not (source / "third-party-notices.txt").is_file():
            raise RuntimeError("Build Workbench first: cd workbench; npm ci; npm run build")
        shutil.copytree(source, Path(self.build_lib) / "zhigou_toolchain" / "workbench_static", dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildWithWorkbench})
