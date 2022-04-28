import atexit
import builtins
import functools

from poetry_dynamic_versioning import (
    _revert_version,
    _get_and_apply_version,
    _get_config_from_path,
    _state,
)


def _patch_poetry_create(factory_mod) -> None:
    original_poetry_create = getattr(factory_mod, "Factory").create_poetry

    try:
        poetry_version_module = _state.original_import_func(
            "poetry.core.semver.version", fromlist=["Version"]
        )
    except ImportError:
        poetry_version_module = _state.original_import_func(
            "poetry.semver.version", fromlist=["Version"]
        )

    @functools.wraps(original_poetry_create)
    def alt_poetry_create(cls, *args, **kwargs):
        instance = original_poetry_create(cls, *args, **kwargs)

        if not _state.patched_poetry_command_run:
            # Fallback if it hasn't been caught by our patched importer already.
            try:
                run_mod = _state.original_import_func(
                    "poetry.console.commands.run", fromlist=[None]
                )
                _patch_poetry_command_run(run_mod)
                _state.patched_poetry_command_run = True
            except (ImportError, AttributeError):
                pass

        if not _state.patched_poetry_command_shell:
            # Fallback if it hasn't been caught by our patched importer already.
            try:
                shell_mod = _state.original_import_func(
                    "poetry.console.commands.shell", fromlist=[None]
                )
                _patch_poetry_command_shell(shell_mod)
                _state.patched_poetry_command_shell = True
            except (ImportError, AttributeError):
                pass

        if not _state.cli_mode:
            name = _get_and_apply_version(
                name=instance.local_config["name"],
                original=instance.local_config["version"],
                pyproject=instance.pyproject.data,
                pyproject_path=instance.pyproject.file,
                cd=True,
            )
            if name:
                version = _state.projects[name].version
                instance._package._version = poetry_version_module.Version.parse(version)
                instance._package._pretty_version = version

        return instance

    getattr(factory_mod, "Factory").create_poetry = alt_poetry_create


def _patch_poetry_command_run(run_mod) -> None:
    original_poetry_command_run = getattr(run_mod, "RunCommand").handle

    @functools.wraps(original_poetry_command_run)
    def alt_poetry_command_run(self, *args, **kwargs):
        # As of Poetry version 1.0.0b2, on Linux, the `poetry run` command
        # uses `os.execvp` function instead of spawning a new process.
        # This prevents the atexit `deactivate` hook to be invoked.
        # For this reason, we immediately call `deactivate` before
        # actually executing the run command.
        deactivate()
        return original_poetry_command_run(self, *args, **kwargs)

    getattr(run_mod, "RunCommand").handle = alt_poetry_command_run


def _patch_poetry_command_shell(shell_mod) -> None:
    original_poetry_command_shell = getattr(shell_mod, "ShellCommand").handle

    @functools.wraps(original_poetry_command_shell)
    def alt_poetry_command_shell(self, *args, **kwargs):
        deactivate()
        return original_poetry_command_shell(self, *args, **kwargs)

    getattr(shell_mod, "ShellCommand").handle = alt_poetry_command_shell


def _patch_builtins_import() -> None:
    """
    We patch the import mechanism to do the rest of the patching for us when
    it sees the relevant imports for Poetry. This is necessary because,
    depending on how Poetry was installed, it may not be available as soon as
    Python starts.
    """

    @functools.wraps(builtins.__import__)
    def alt_import(name, globals=None, locals=None, fromlist=(), level=0):
        module = _state.original_import_func(name, globals, locals, fromlist, level)

        if not _state.patched_poetry_create:
            try:
                if name == "poetry.factory" and fromlist:
                    _patch_poetry_create(module)
                    _state.patched_poetry_create = True
                elif name == "poetry" and "factory" in fromlist:
                    _patch_poetry_create(module.factory)
                    _state.patched_poetry_create = True
            except (ImportError, AttributeError):
                pass

        if not _state.patched_core_poetry_create:
            try:
                if name == "poetry.core.factory" and fromlist:
                    _patch_poetry_create(module)
                    _state.patched_core_poetry_create = True
                elif name == "poetry.core" and "factory" in fromlist:
                    _patch_poetry_create(module.factory)
                    _state.patched_core_poetry_create = True
            except (ImportError, AttributeError):
                pass

        if not _state.patched_poetry_command_run:
            try:
                if name == "poetry.console.commands.run" and fromlist:
                    _patch_poetry_command_run(module)
                    _state.patched_poetry_command_run = True
                elif name == "poetry.console.commands" and "run" in fromlist:
                    _patch_poetry_command_run(module.run)
                    _state.patched_poetry_command_run = True
            except (ImportError, AttributeError):
                pass

        if not _state.patched_poetry_command_shell:
            try:
                if name == "poetry.console.commands.shell" and fromlist:
                    _patch_poetry_command_shell(module)
                    _state.patched_poetry_command_shell = True
                elif name == "poetry.console.commands" and "shell" in fromlist:
                    _patch_poetry_command_shell(module.shell)
                    _state.patched_poetry_command_shell = True
            except (ImportError, AttributeError):
                pass

        return module

    builtins.__import__ = alt_import


def _apply_patches() -> None:
    # Use the least invasive patching if possible; otherwise, wait until
    # Poetry is available to be patched.
    need_fallback_patches = False

    if not _state.patched_poetry_create:
        try:
            from poetry import factory as factory_mod

            _patch_poetry_create(factory_mod)
            _state.patched_poetry_create = True
        except ImportError:
            need_fallback_patches = True

    if not _state.patched_core_poetry_create:
        try:
            from poetry.core import factory as core_factory_mod

            _patch_poetry_create(core_factory_mod)
            _state.patched_core_poetry_create = True
        except ImportError:
            need_fallback_patches = True

    if not _state.patched_poetry_command_run:
        try:
            from poetry.console.commands import run as run_mod

            _patch_poetry_command_run(run_mod)
            _state.patched_poetry_command_run = True
        except ImportError:
            need_fallback_patches = True

    if not _state.patched_poetry_command_shell:
        try:
            from poetry.console.commands import shell as shell_mod

            _patch_poetry_command_shell(shell_mod)
            _state.patched_poetry_command_shell = True
        except ImportError:
            need_fallback_patches = True

    if need_fallback_patches:
        _patch_builtins_import()


def activate() -> None:
    config = _get_config_from_path()
    if not config["enable"]:
        return

    _apply_patches()
    atexit.register(deactivate)


def deactivate() -> None:
    if not _state.cli_mode:
        _revert_version()
