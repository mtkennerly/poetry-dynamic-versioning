import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence, Tuple

import pytest

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
DUMMY = ROOT / "tests" / "project"
DUMMY_DIST = DUMMY / "dist"
DUMMY_PYPROJECT = DUMMY / "pyproject.toml"

DUMMY_VERSION = "0.0.999"
DEPENDENCY_DYNAMIC_VERSION = "0.0.888"


def run(
    command: str,
    codes: Sequence[int] = (0,),
    where: Optional[Path] = None,
    shell: bool = False,
    env: Optional[dict] = None,
) -> Tuple[int, str]:
    split = shlex.split(command)

    if split[0] == "poetry":
        split[0] = os.environ.get("POETRY", "poetry")

    result = subprocess.run(
        split,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(where) if where is not None else None,
        shell=shell,
        env={**os.environ, **env} if env else None,
    )
    output = result.stdout.decode("utf-8", errors="ignore").strip()
    if codes and result.returncode not in codes:
        raise RuntimeError(
            "The command '{}' returned code {}. Output:\n{}".format(
                command, result.returncode, output
            )
        )
    return (result.returncode, output)


def delete(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()


@pytest.fixture(scope="module", autouse=True)
def before_all():
    run("poetry self remove poetry-dynamic-versioning", codes=[0, 1])
    delete(DIST)
    delete(DUMMY / ".venv")
    run("poetry build", where=ROOT)
    artifact = next(DIST.glob("*.whl"))
    run(f'poetry self add "{artifact}[plugin]"')

    yield

    run(f'git checkout -- "{DUMMY.as_posix()}" "{ROOT.as_posix()}/tests/dependency-*"')
    run("poetry self remove poetry-dynamic-versioning", codes=[0, 1])


@pytest.fixture(autouse=True)
def before_each():
    run(f"git checkout -- {DUMMY.as_posix()}")
    delete(DUMMY / "dist")
    delete(DUMMY / "poetry.lock")
    for file in DUMMY.glob("*.whl"):
        delete(file)


def test_plugin_enabled():
    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION not in artifact.name


def test_plugin_disabled():
    data = DUMMY_PYPROJECT.read_text("utf8")
    data = data.replace("enable = true", "enable = false")
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION in artifact.name


def test_plugin_disabled_without_plugin_section():
    data = DUMMY_PYPROJECT.read_text("utf8")
    data = data.replace("[tool.poetry-dynamic-versioning]", "[tool.poetry-dynamic-versioning-x]")
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION in artifact.name


def test_plugin_disabled_without_pyproject_file():
    delete(DUMMY_PYPROJECT)
    run("poetry --help", where=DUMMY)


def test_invalid_config_for_vcs():
    data = DUMMY_PYPROJECT.read_text("utf8")
    data = data.replace('vcs = "git"', 'vcs = "invalid"')
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY, codes=[1])


def test_keep_pyproject_modifications():
    package = "cachy"
    # Using --optional to avoid actually installing the package
    run(f"poetry add --optional {package}", where=DUMMY)
    # Make sure pyproject.toml contains the new package dependency
    data = DUMMY_PYPROJECT.read_text("utf8")
    assert package in data


def test_poetry_run():
    # The original version is restored before the command runs:
    run(f"poetry run grep 'version = \"{DUMMY_VERSION}\"' pyproject.toml", where=DUMMY)
    # Make sure original version number is still in place:
    data = DUMMY_PYPROJECT.read_text("utf8")
    assert f'version = "{DUMMY_VERSION}"' in data


@pytest.mark.skipif("CI" in os.environ, reason="Avoid error: 'Inappropriate ioctl for device'")
def test_poetry_shell():
    # Make sure original version number is still in place afterwards:
    run("poetry shell", where=DUMMY)
    data = DUMMY_PYPROJECT.read_text("utf8")
    assert f'version = "{DUMMY_VERSION}"' in data


def test_plugin_cli_mode_and_substitution():
    run("poetry dynamic-versioning", where=DUMMY)
    # Changes persist after the command is done:
    assert f'version = "{DUMMY_VERSION}"' not in DUMMY_PYPROJECT.read_text("utf8")
    assert '__version__: str = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert '__version__ = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert "__version_tuple__ = (0, 0, 0)" not in (DUMMY / "project" / "__init__.py").read_text(
        "utf8"
    )
    assert "<0.0.0>" not in (DUMMY / "project" / "__init__.py").read_text("utf8")


def test_standalone_cli_mode_and_substitution():
    run("poetry-dynamic-versioning", where=DUMMY)
    # Changes persist after the command is done:
    assert f'version = "{DUMMY_VERSION}"' not in DUMMY_PYPROJECT.read_text("utf8")
    assert '__version__: str = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert '__version__ = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert "__version_tuple__ = (0, 0, 0)" not in (DUMMY / "project" / "__init__.py").read_text(
        "utf8"
    )
    assert "<0.0.0>" not in (DUMMY / "project" / "__init__.py").read_text("utf8")


def test_cli_mode_and_substitution_without_enable():
    data = DUMMY_PYPROJECT.read_text("utf8")
    data = data.replace("enable = true", "enable = false")
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry dynamic-versioning", where=DUMMY)
    # Changes persist after the command is done:
    assert f'version = "{DUMMY_VERSION}"' not in DUMMY_PYPROJECT.read_text("utf8")
    assert '__version__: str = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert '__version__ = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert "__version_tuple__ = (0, 0, 0)" not in (DUMMY / "project" / "__init__.py").read_text(
        "utf8"
    )
    assert "<0.0.0>" not in (DUMMY / "project" / "__init__.py").read_text("utf8")


def test_dependency_versions():
    run("poetry install", where=DUMMY)
    _, out = run("poetry run pip list --format freeze", where=DUMMY)
    assert "dependency-dynamic==" in out
    assert f"dependency-dynamic=={DEPENDENCY_DYNAMIC_VERSION}" not in out
    assert "dependency-static==0.0.777" in out
    assert "dependency-classic==0.0.666" in out


def test_poetry_core_as_build_system():
    project = ROOT / "tests" / "dependency-dynamic"
    dist = project / "dist"
    pyproject = project / "pyproject.toml"

    data = pyproject.read_text("utf8")
    data = re.sub(
        r"requires = .*",
        'requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning"]',
        data,
    )
    data = re.sub(
        r"build-backend = .*",
        'build-backend = "poetry_dynamic_versioning.backend"',
        data,
    )
    pyproject.write_bytes(data.encode("utf-8"))

    run("pip wheel . --no-build-isolation --wheel-dir dist", where=project)
    artifact = next(dist.glob("*.whl"))
    assert DEPENDENCY_DYNAMIC_VERSION not in artifact.name


def test_bumping_enabled():
    data = DUMMY_PYPROJECT.read_text("utf8")
    data = data.replace('vcs = "git"', "bump = true")
    data = data.replace('style = "semver"', 'style = "pep440"')
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION not in artifact.name
    assert ".post" not in artifact.name


def test_bypass():
    run("poetry build", where=DUMMY, env={"POETRY_DYNAMIC_VERSIONING_BYPASS": "1.2.3"})
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert "-1.2.3-" in artifact.name


def test_plugin_show():
    _, out = run("poetry self show")

    # This is flaky during CI for some reason.
    # There's no error from Poetry, but the plugin isn't always listed,
    # even though it's installed and usable.
    # Just skip it for now.
    if "CI" not in os.environ:
        assert "poetry-dynamic-versioning" in out
