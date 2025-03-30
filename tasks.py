import os
import re
import shutil
import sys
import datetime as dt
from pathlib import Path

from invoke import task

ROOT = Path(__file__).parent
PYPROJECT = ROOT / "pyproject.toml"

NORMAL_PYPROJECT = ROOT / "pyproject.patch.toml"
DEPRECATED_PYPROJECT = ROOT / "pyproject.plugin.toml"


def get_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text("utf-8").splitlines():
        if line.startswith("version ="):
            return line.replace("version = ", "").strip('"')

    raise RuntimeError("Could not determine version")


def replace_pattern_in_file(file: Path, old: str, new: str, count: int = 1):
    content = file.read_text("utf-8")
    updated = re.sub(old, new, content, count=count)
    file.write_text(updated, "utf-8")


def confirm(prompt: str):
    response = input(f"Confirm by typing '{prompt}': ")
    if response.lower() != prompt.lower():
        sys.exit(1)


@task
def pdv(ctx):
    if NORMAL_PYPROJECT.exists():
        PYPROJECT.rename(DEPRECATED_PYPROJECT)
        NORMAL_PYPROJECT.rename(PYPROJECT)


@task
def pdvp(ctx):
    if DEPRECATED_PYPROJECT.exists():
        PYPROJECT.rename(NORMAL_PYPROJECT)
        DEPRECATED_PYPROJECT.rename(PYPROJECT)


@task
def build(ctx, clean=True):
    with ctx.cd(ROOT):
        if clean:
            shutil.rmtree("dist", ignore_errors=True)
        ctx.run("poetry build")


@task
def test(ctx, unit=False, integration=False, pattern=None, pipx=False):
    all = not unit and not integration

    # This ensures we use the global Poetry instead of the venv's Poetry:
    os.environ.update({"POETRY": shutil.which("poetry")})

    if pipx:
        os.environ.update({"POETRY_DYNAMIC_VERSIONING_TEST_INSTALLATION": "pipx"})

    if pattern is None:
        pattern = ""
    else:
        pattern = "-k {}".format(pattern)

    with ctx.cd(ROOT):
        if unit or all:
            ctx.run("poetry run pytest tests/test_unit.py {}".format(pattern))
        if integration or all:
            ctx.run("poetry run pytest tests/test_integration.py {}".format(pattern))


@task
def install(ctx, pip=False, pipx=False):
    with ctx.cd(ROOT):
        uninstall(ctx, pip, pipx)
        build(ctx)
        wheel = next(ROOT.glob("dist/*.whl"))
        if pip:
            ctx.run('pip install "{}[plugin]"'.format(wheel))
        elif pipx:
            ctx.run('pipx inject poetry "{}[plugin]"'.format(wheel))
        else:
            ctx.run('poetry self add "{}[plugin]"'.format(wheel))


@task
def uninstall(ctx, pip=False, pipx=False):
    try:
        if pip:
            ctx.run("pip uninstall -y poetry-dynamic-versioning")
        elif pipx:
            ctx.run("pipx uninject poetry poetry-dynamic-versioning")
        else:
            ctx.run("poetry self remove poetry-dynamic-versioning")
    except Exception:
        pass


@task
def docs(ctx):
    version = get_version()
    manpage = "docs/poetry-dynamic-versioning.1"

    args = [
        "poetry",
        "run",
        "argparse-manpage",
        "--pyfile",
        "poetry_dynamic_versioning/cli.py",
        "--function",
        "get_parser",
        "--project-name",
        "poetry-dynamic-versioning - Dynamic versioning plugin for Poetry",
        "--prog",
        "poetry-dynamic-versioning",
        "--version",
        version,
        "--author",
        "Matthew T. Kennerly (mtkennerly)",
        "--url",
        "https://github.com/mtkennerly/poetry-dynamic-versioning",
        "--format",
        "single-commands-section",
        "--output",
        manpage,
        "--manual-title",
        "poetry-dynamic-versioning",
    ]

    # Join manually to avoid issues with single quotes on Windows using `shlex.join`
    joined = " ".join(arg if " " not in arg else f'"{arg}"' for arg in args)

    ctx.run(joined)


@task
def prerelease(ctx, new_version):
    date = dt.datetime.now().strftime("%Y-%m-%d")

    replace_pattern_in_file(
        ROOT / "pyproject.toml",
        'version = ".+"',
        f'version = "{new_version}"',
    )

    replace_pattern_in_file(
        ROOT / "CHANGELOG.md",
        "## Unreleased",
        f"## v{new_version} ({date})",
    )

    build(ctx, clean=True)
    docs(ctx)


@task
def release(ctx):
    version = get_version()

    confirm(f"release {version}")

    ctx.run(f'git commit -m "Release v{version}"')
    ctx.run(f'git tag v{version} -m "Release"')
    ctx.run("git push")
    ctx.run("git push origin tag v{version}")

    ctx.run("poetry publish")
