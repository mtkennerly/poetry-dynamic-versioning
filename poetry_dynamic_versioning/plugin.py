__all__ = [
    "DynamicVersioningCommand",
    "DynamicVersioningPlugin",
]

import functools
import os
import sys

from cleo.commands.command import Command
from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.event_dispatcher import EventDispatcher
from cleo.events.console_events import COMMAND, SIGNAL, TERMINATE, ERROR
from packaging.version import Version as PackagingVersion
from poetry.core import __version__ as poetry_core_version
from poetry.core.poetry import Poetry
from poetry.core.factory import Factory
from poetry.console.application import Application
from poetry.plugins.application_plugin import ApplicationPlugin

if PackagingVersion(poetry_core_version) >= PackagingVersion("1.3.0"):
    from poetry.core.constraints.version import Version as PoetryCoreVersion
else:
    from poetry.core.semver.version import Version as PoetryCoreVersion


from poetry_dynamic_versioning import (
    _get_config,
    _get_and_apply_version,
    _state,
    _revert_version,
    _validate_config,
)

_COMMAND_ENV = "POETRY_DYNAMIC_VERSIONING_COMMANDS"


def _patch_dependency_versions() -> None:
    """
    The plugin system doesn't seem to expose a way to change dependency
    versions, so we patch `Factory.create_poetry()` to do the work there.
    """
    if _state.patched_core_poetry_create:
        return

    original_create_poetry = Factory.create_poetry

    @functools.wraps(Factory.create_poetry)
    def patched_create_poetry(*args, **kwargs):
        instance = original_create_poetry(*args, **kwargs)
        _apply_version_via_plugin(instance)
        return instance

    Factory.create_poetry = patched_create_poetry
    _state.patched_core_poetry_create = True


def _should_apply(command: str) -> bool:
    override = os.environ.get(_COMMAND_ENV)
    if override is not None:
        return command in override.split(",")
    else:
        return command not in ["run", "shell", "dynamic-versioning"]


def _apply_version_via_plugin(poetry: Poetry, retain: bool = False, force: bool = False) -> None:
    name = _get_and_apply_version(
        name=poetry.local_config["name"],
        original=poetry.local_config["version"],
        pyproject=poetry.pyproject.data,
        pyproject_path=poetry.pyproject.file,
        retain=retain,
        force=force,
    )
    if name:
        version = _state.projects[name].version

        # Would be nice to use `.set_version()`, but it's only available on
        # Poetry's `ProjectPackage`, not poetry-core's `ProjectPackage`.
        poetry._package._version = PoetryCoreVersion.parse(version)
        poetry._package._pretty_version = version


class DynamicVersioningCommand(Command):
    name = "dynamic-versioning"
    description = (
        "Apply the dynamic version to all relevant files and leave the changes in-place."
        " This allows you to activate the plugin behavior on demand and inspect the result."
    )

    def __init__(self, application: Application):
        super().__init__()
        self._application = application

    def handle(self) -> int:
        _state.cli_mode = True
        _apply_version_via_plugin(self._application.poetry, retain=True, force=True)
        return 0


class DynamicVersioningPlugin(ApplicationPlugin):
    def __init__(self):
        self._application = None

    def activate(self, application: Application) -> None:
        self._application = application

        application.command_loader.register_factory(
            "dynamic-versioning", lambda: DynamicVersioningCommand(application)
        )

        try:
            local = self._application.poetry.pyproject.data
        except RuntimeError:
            # We're not in a Poetry project directory
            return

        errors = _validate_config(local)
        if errors:
            print("poetry-dynamic-versioning configuration issues:", file=sys.stderr)
            for error in errors:
                print("  - {}".format(error), file=sys.stderr)

        config = _get_config(local)
        if not config["enable"]:
            return

        application.event_dispatcher.add_listener(COMMAND, self._apply_version)
        application.event_dispatcher.add_listener(SIGNAL, self._revert_version)
        application.event_dispatcher.add_listener(TERMINATE, self._revert_version)
        application.event_dispatcher.add_listener(ERROR, self._revert_version)

    def _apply_version(
        self, event: ConsoleCommandEvent, kind: str, dispatcher: EventDispatcher
    ) -> None:
        if not _should_apply(event.command.name):
            return

        _apply_version_via_plugin(self._application.poetry)
        _patch_dependency_versions()

    def _revert_version(
        self, event: ConsoleCommandEvent, kind: str, dispatcher: EventDispatcher
    ) -> None:
        if not _should_apply(event.command.name):
            return

        _revert_version()
