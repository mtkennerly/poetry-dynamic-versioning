import os
import shutil
from pathlib import Path

from invoke import task

ROOT = Path(__file__).parent
PYPROJECT = ROOT / "pyproject.toml"

NORMAL_PYPROJECT = ROOT / "pyproject.patch.toml"
DEPRECATED_PYPROJECT = ROOT / "pyproject.plugin.toml"


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
def test(ctx, unit=False, integration=False):
    all = not unit and not integration

    # This ensures we use the global Poetry instead of the venv's Poetry:
    os.environ.update({"POETRY": shutil.which("poetry")})

    with ctx.cd(ROOT):
        if unit or all:
            ctx.run("poetry run pytest tests/test_unit.py")
        if integration or all:
            ctx.run("poetry run pytest tests/test_integration.py")


@task
def install(ctx):
    with ctx.cd(ROOT):
        uninstall(ctx)
        build(ctx)
        wheel = next(ROOT.glob("dist/*.whl"))
        ctx.run('poetry self add "{}[plugin]"'.format(wheel))


@task
def uninstall(ctx):
    try:
        ctx.run("poetry self remove poetry-dynamic-versioning")
    except Exception:
        pass
