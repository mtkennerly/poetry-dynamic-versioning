import shutil
from pathlib import Path

from invoke import task

ROOT = Path(__file__).parent
PYPROJECT = ROOT / "pyproject.toml"
PATCH = ROOT / "pyproject.patch.toml"
PLUGIN = ROOT / "pyproject.plugin.toml"


@task
def patch(ctx):
    if PATCH.exists():
        PYPROJECT.rename(PLUGIN)
        PATCH.rename(PYPROJECT)
        with ctx.cd(ROOT):
            ctx.run("poetry install")


@task
def plugin(ctx):
    if PLUGIN.exists():
        PYPROJECT.rename(PATCH)
        PLUGIN.rename(PYPROJECT)
        with ctx.cd(ROOT):
            ctx.run("poetry install")


@task
def build(ctx):
    with ctx.cd(ROOT):
        shutil.rmtree("dist", ignore_errors=True)
        ctx.run("poetry build")


@task
def test(ctx):
    with ctx.cd(ROOT):
        mode = "patch" if PLUGIN.exists() else "plugin"
        ctx.run("poetry run pytest")
        ctx.run("bash ./tests/integration.sh {}".format(mode))


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
