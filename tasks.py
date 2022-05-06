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
    with ctx.cd(ROOT):
        ctx.run("poetry install")


@task
def plugin(ctx):
    switch_to_plugin()
    with ctx.cd(ROOT):
        ctx.run("poetry install")


@task
def build(ctx):
    with ctx.cd(ROOT):
        shutil.rmtree("dist", ignore_errors=True)
        ctx.run("poetry build")


@task
def test(ctx, unit=False, integration=False, installation="pip", name=None):
    all = not unit and not integration
    with ctx.cd(ROOT):
        mode = "patch" if PLUGIN_PYPROJECT.exists() else "plugin"
        if unit or all:
            ctx.run("poetry run pytest")
        if integration or all:
            ctx.run("bash ./tests/integration.sh {} {} {}".format(mode, installation, name or ""))


@task
def install(ctx):
    with ctx.cd(ROOT):
        uninstall(ctx)
        build(ctx)
        wheel = next(ROOT.glob("dist/*.whl"))
        ctx.run('pip install "{}"'.format(wheel))


@task
def uninstall(ctx):
    ctx.run("pip uninstall -y poetry-dynamic-versioning poetry-dynamic-versioning-plugin")


@task
def release(ctx, patch=False, plugin=False):
    started_as_patch = PLUGIN_PYPROJECT.exists()

    if patch:
        switch_to_patch()
        build(ctx)
    if plugin:
        switch_to_plugin()
        build(ctx)

    if started_as_patch:
        switch_to_patch()
