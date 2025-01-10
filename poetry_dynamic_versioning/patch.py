import atexit
import functools

from poetry_dynamic_versioning import (
    _revert_version,
    _get_and_apply_version,
    _get_config_from_path,
    _get_pyproject_path_from_poetry,
    _state,
)


def _patch_poetry_create(factory_mod) -> None:
    try:
        from poetry.core.constraints.version import Version as PoetryVersion
    except ImportError:
        from poetry.core.semver.version import Version as PoetryVersion

    original_poetry_create = getattr(factory_mod, "Factory").create_poetry

    @functools.wraps(original_poetry_create)
    def alt_poetry_create(cls, *args, **kwargs):
        instance = original_poetry_create(cls, *args, **kwargs)

        if not _state.cli_mode:
            name = _get_and_apply_version(
                pyproject_path=_get_pyproject_path_from_poetry(instance.pyproject),
            )
            if name:
                version = _state.projects[name].version
                instance._package._version = PoetryVersion.parse(version)
                instance._package._pretty_version = version

        return instance

    getattr(factory_mod, "Factory").create_poetry = alt_poetry_create


def _apply_patches() -> None:
    if not _state.patched_core_poetry_create:
        from poetry.core import factory as factory_mod

        _patch_poetry_create(factory_mod)
        _state.patched_core_poetry_create = True


def activate() -> None:
    config = _get_config_from_path()
    if not config["enable"]:
        return

    _apply_patches()
    atexit.register(deactivate)


def deactivate() -> None:
    if not _state.cli_mode:
        _revert_version()
