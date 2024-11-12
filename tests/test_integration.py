import os
import re
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Optional, Sequence, Tuple

import dunamai
import pytest
import tomlkit

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
DUMMY = ROOT / "tests" / "project"
DUMMY_DIST = DUMMY / "dist"
DUMMY_PYPROJECT = DUMMY / "pyproject.toml"

DUMMY_PEP621 = ROOT / "tests" / "project-pep621"
DUMMY_PEP621_DIST = DUMMY_PEP621 / "dist"
DUMMY_PEP621_PYPROJECT = DUMMY_PEP621 / "pyproject.toml"

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
        raise RuntimeError("The command '{}' returned code {}. Output:\n{}".format(command, result.returncode, output))
    return (result.returncode, output)


def delete(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()


def install_plugin(artifact: str) -> None:
    pipx = os.environ.get("POETRY_DYNAMIC_VERSIONING_TEST_INSTALLATION") == "pipx"

    if pipx:
        run(f'pipx inject poetry "{artifact}[plugin]"')
    else:
        run(f'poetry self add "{artifact}[plugin]"')


def uninstall_plugin() -> None:
    pipx = os.environ.get("POETRY_DYNAMIC_VERSIONING_TEST_INSTALLATION") == "pipx"

    if pipx:
        run("pipx uninject poetry poetry-dynamic-versioning", codes=[0, 1])
    else:
        run("poetry self remove poetry-dynamic-versioning", codes=[0, 1])


@pytest.fixture(scope="module", autouse=True)
def before_all():
    uninstall_plugin()
    delete(DIST)
    delete(DUMMY / ".venv")
    run("poetry build", where=ROOT)
    artifact = next(DIST.glob("*.whl"))
    install_plugin(artifact)

    yield

    run(f'git checkout -- "{DUMMY.as_posix()}" "{ROOT.as_posix()}/tests/dependency-*"')
    uninstall_plugin()


@pytest.fixture(autouse=True)
def before_each():
    for project in [DUMMY, DUMMY_PEP621]:
        run(f"git checkout -- {project.as_posix()}")
        delete(project / "dist")
        delete(project / "poetry.lock")
        for file in project.glob("*.whl"):
            delete(file)


def test_plugin_enabled():
    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION not in artifact.name


def test_plugin_disabled():
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    data = data.replace("enable = true", "enable = false")
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION in artifact.name


def test_plugin_disabled_without_plugin_section():
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    data = data.replace("[tool.poetry-dynamic-versioning]", "[tool.poetry-dynamic-versioning-x]")
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.whl"))
    assert DUMMY_VERSION in artifact.name


def test_plugin_disabled_without_pyproject_file():
    delete(DUMMY_PYPROJECT)
    run("poetry --help", where=DUMMY)


def test_invalid_config_for_vcs():
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    data = data.replace('vcs = "git"', 'vcs = "invalid"')
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry build", where=DUMMY, codes=[1])


def test_keep_pyproject_modifications():
    package = "cachy"
    # Using --optional to avoid actually installing the package
    if "USE_PEP621" in os.environ:
        run(f"poetry add --optional main {package}", where=DUMMY)
    else:
        run(f"poetry add --optional {package}", where=DUMMY)
    # Make sure pyproject.toml contains the new package dependency
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    assert package in data


def test_poetry_run():
    # The original version is restored before the command runs:
    run(f"poetry run grep 'version = \"{DUMMY_VERSION}\"' pyproject.toml", where=DUMMY)
    # Make sure original version number is still in place:
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    assert f'version = "{DUMMY_VERSION}"' in data


@pytest.mark.skipif("CI" in os.environ, reason="Avoid error: 'Inappropriate ioctl for device'")
def test_poetry_shell():
    # Make sure original version number is still in place afterwards:
    run("poetry shell", where=DUMMY)
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    assert f'version = "{DUMMY_VERSION}"' in data


def test_plugin_cli_mode_and_substitution():
    run("poetry dynamic-versioning", where=DUMMY)
    # Changes persist after the command is done:
    assert f'version = "{DUMMY_VERSION}"' not in DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    assert '__version__: str = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")
    assert '__version__ = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")
    assert "__version_tuple__ = (0, 0, 0)" not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert "<0.0.0>" not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")


def test_standalone_cli_mode_and_substitution():
    run("poetry-dynamic-versioning", where=DUMMY)
    # Changes persist after the command is done:
    assert f'version = "{DUMMY_VERSION}"' not in DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    assert '__version__: str = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")
    assert '__version__ = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")
    assert "__version_tuple__ = (0, 0, 0)" not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert "<0.0.0>" not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")


def test_cli_mode_and_substitution_without_enable():
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    data = data.replace("enable = true", "enable = false")
    DUMMY_PYPROJECT.write_bytes(data.encode("utf-8"))

    run("poetry dynamic-versioning", where=DUMMY)
    # Changes persist after the command is done:
    assert f'version = "{DUMMY_VERSION}"' not in DUMMY_PYPROJECT.read_bytes().decode("utf-8")
    assert '__version__: str = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")
    assert '__version__ = "0.0.0"' not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")
    assert "__version_tuple__ = (0, 0, 0)" not in (DUMMY / "project" / "__init__.py").read_text("utf8")
    assert "<0.0.0>" not in (DUMMY / "project" / "__init__.py").read_bytes().decode("utf-8")


def test_cli_mode_plus_build_will_disable_plugin():
    run("poetry dynamic-versioning", where=DUMMY)
    run("poetry build", where=DUMMY)
    artifact = next(DUMMY_DIST.glob("*.tar.gz"))
    with tarfile.open(artifact, "r:gz") as f:
        item = "{}/pyproject.toml".format(artifact.name.replace(".tar.gz", ""))
        content = f.extractfile(item).read()
        parsed = tomlkit.parse(content)
        assert parsed["tool"]["poetry-dynamic-versioning"]["enable"] is False


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

    data = pyproject.read_bytes().decode("utf-8")
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
    data = DUMMY_PYPROJECT.read_bytes().decode("utf-8")
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


@pytest.mark.skipif("CI" in os.environ, reason="CI uses Pipx, which doesn't play nice with this 'poetry self'")
def test_plugin_show():
    _, out = run("poetry self show")
    assert "poetry-dynamic-versioning" in out


@pytest.mark.skipif("USE_PEP621" not in os.environ, reason="Requires Poetry with PEP-621 support")
def test_pep621_with_dynamic_version():
    version = dunamai.Version.from_git().serialize()

    run("poetry-dynamic-versioning", where=DUMMY_PEP621)
    pyproject = tomlkit.parse(DUMMY_PEP621_PYPROJECT.read_bytes().decode("utf-8"))
    assert pyproject["project"]["version"] == version
    assert "version" not in pyproject["project"]["dynamic"]
    assert f'__version__ = "{version}"' in (DUMMY_PEP621 / "project_pep621" / "__init__.py").read_bytes().decode(
        "utf-8"
    )


@pytest.mark.skipif("USE_PEP621" not in os.environ, reason="Requires Poetry with PEP-621 support")
def test_pep621_with_dynamic_version_and_cleanup():
    version = dunamai.Version.from_git().serialize()

    run("poetry build", where=DUMMY_PEP621)
    pyproject = tomlkit.parse(DUMMY_PEP621_PYPROJECT.read_bytes().decode("utf-8"))
    assert "version" not in pyproject["project"]
    assert "version" in pyproject["project"]["dynamic"]
    assert '__version__ = "0.0.0"' in (DUMMY_PEP621 / "project_pep621" / "__init__.py").read_bytes().decode("utf-8")

    artifact = next(DUMMY_PEP621_DIST.glob("*.whl"))
    assert f"-{version}-" in artifact.name


@pytest.mark.skipif("USE_PEP621" not in os.environ, reason="Requires Poetry with PEP-621 support")
def test_pep621_without_dynamic_version():
    pyproject = tomlkit.parse(DUMMY_PEP621_PYPROJECT.read_bytes().decode("utf-8"))
    pyproject["project"]["dynamic"] = []
    DUMMY_PEP621_PYPROJECT.write_bytes(tomlkit.dumps(pyproject).encode("utf-8"))

    run("poetry-dynamic-versioning", codes=[1], where=DUMMY_PEP621)
    pyproject = tomlkit.parse(DUMMY_PEP621_PYPROJECT.read_bytes().decode("utf-8"))
    assert "version" not in pyproject["project"]
    assert '__version__ = "0.0.0"' in (DUMMY_PEP621 / "project_pep621" / "__init__.py").read_bytes().decode("utf-8")
