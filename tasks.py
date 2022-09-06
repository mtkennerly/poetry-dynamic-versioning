import os
import shutil
from pathlib import Path

from invoke import task

ROOT = Path(__file__).parent
PYPROJECT = ROOT / "pyproject.toml"
LOCK = ROOT / "poetry.lock"

PATCH_PYPROJECT = ROOT / "pyproject.patch.toml"
PLUGIN_PYPROJECT = ROOT / "pyproject.plugin.toml"
PATCH_LOCK = ROOT / "poetry.patch.lock"
PLUGIN_LOCK = ROOT / "poetry.plugin.lock"


def switch_to_patch():
    if PATCH_PYPROJECT.exists():
        PYPROJECT.rename(PLUGIN_PYPROJECT)
        PATCH_PYPROJECT.rename(PYPROJECT)
    if PATCH_LOCK.exists():
        LOCK.rename(PLUGIN_LOCK)
        PATCH_LOCK.rename(LOCK)


def switch_to_plugin():
    if PLUGIN_PYPROJECT.exists():
        PYPROJECT.rename(PATCH_PYPROJECT)
        PLUGIN_PYPROJECT.rename(PYPROJECT)
    if PLUGIN_LOCK.exists():
        LOCK.rename(PATCH_LOCK)
        PLUGIN_LOCK.rename(LOCK)


@task
def patch(ctx):
    switch_to_patch()


@task
def plugin(ctx):
    switch_to_plugin()


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
    ctx.run("poetry self remove poetry-dynamic-versioning")


@task
def release(ctx, patch=False, plugin=False):
    started_as_patch = PLUGIN_PYPROJECT.exists()
    clean = True

    if patch:
        switch_to_patch()
        build(ctx, clean)
        clean = False
    if plugin:
        switch_to_plugin()
        build(ctx, clean)

    if started_as_patch:
        switch_to_patch()
