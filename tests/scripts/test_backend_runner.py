"""Runner unit check: never reuse/delete an earlier basetemp or lose exit status."""
import sys
from pathlib import Path

import pytest

from tools import run_backend_tests


def test_backend_runner_owns_unique_existing_parent_and_propagates_failure(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(run_backend_tests.__file__).parent))
    import verify_release_candidate
    calls = []
    def observed(directory, name, command, *, pytest_run):
        temp = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--basetemp=")))
        assert temp.parent.is_dir() and not temp.exists()
        assert temp.is_relative_to(tmp_path)
        assert name == "run" and pytest_run is True
        calls.append(temp)
        return {"exit_code": 23}
    monkeypatch.setattr(run_backend_tests, "ROOT", tmp_path)
    monkeypatch.setattr(verify_release_candidate, "run", observed)
    assert run_backend_tests.main([]) == run_backend_tests.main([]) == 23
    assert len(calls) == 2 and calls[0] != calls[1]


@pytest.mark.parametrize(("arguments", "code"), [(["--help"], 0), (["--typo"], 2)])
def test_backend_runner_help_and_invalid_arguments_never_start_tests(tmp_path, monkeypatch, arguments, code):
    monkeypatch.setattr(run_backend_tests, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as exc:
        run_backend_tests.main(arguments)
    assert exc.value.code == code
    assert not list(tmp_path.iterdir())
