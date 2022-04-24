__all__ = [
    "DynamicVersioningCommand",
    "DynamicVersioningPlugin",
]

import functools

from cleo.commands.command import Command
from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.event_dispatcher import EventDispatcher
from cleo.events.console_events import COMMAND, SIGNAL, TERMINATE, ERROR
from poetry.core.poetry import Poetry
from poetry.core.factory import Factory
from poetry.core.semver.version import Version as PoetryCoreVersion
from poetry.console.application import Application
from poetry.plugins.application_plugin import ApplicationPlugin

from poetry_dynamic_versioning import (
    _get_config,
    _get_version,
    _apply_version,
    _state,
    _revert_version,
    _ProjectState,
)


def _patch_dependency_versions() -> None:
    """
    The plugin system doesn't seem to expose a way to change dependency
    versions, so we patch `Factory.create_poetry()` to do the work there.
    """
    if _state.patched:
        return

    original_create_poetry = Factory.create_poetry

    @functools.wraps(Factory.create_poetry)
    def patched_create_poetry(*args, **kwargs):
        instance = original_create_poetry(*args, **kwargs)
        _apply_version_via_plugin(instance, retain=False)
        return instance

    Factory.create_poetry = patched_create_poetry
    _state.patched = True


def _should_apply(command: str) -> bool:
    return command not in ["run", "shell", "dynamic-versioning"]


def _apply_version_via_plugin(poetry: Poetry, retain: bool) -> None:
    config = _get_config(poetry.pyproject.data)
    if not config["enable"]:
        return
    name = poetry.local_config["name"]
    if name in _state.projects:
        return
    version = _get_version(config)
    _state.projects[name] = _ProjectState(
        poetry.file.path, poetry.local_config["version"], version, None,
    )

    # Would be nice to use `.set_version()`, but it's only available on
    # Poetry's `ProjectPackage`, not poetry-core's `ProjectPackage`.
    poetry._package._version = PoetryCoreVersion.parse(version)
    poetry._package._pretty_version = version

    _apply_version(
        version, config, poetry.file.path, retain,
    )


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
        _apply_version_via_plugin(self._application.poetry, retain=True)
        return 0


class DynamicVersioningPlugin(ApplicationPlugin):
    def __init__(self):
        self._application = None

    def activate(self, application: Application) -> None:
        self._application = application

        application.command_loader.register_factory(
            "dynamic-versioning", lambda: DynamicVersioningCommand(application)
        )

        config = _get_config(self._application.poetry.pyproject.data)
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

        _apply_version_via_plugin(self._application.poetry, retain=False)
        _patch_dependency_versions()

    def _revert_version(
        self, event: ConsoleCommandEvent, kind: str, dispatcher: EventDispatcher
    ) -> None:
        if not _should_apply(event.command.name):
            return

        _revert_version()
