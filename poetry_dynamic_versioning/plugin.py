__all__ = [
    "DynamicVersioningCommand",
    "DynamicVersioningPlugin",
]

from poetry_dynamic_versioning import (
    _get_config,
    _get_version,
    _apply_version,
    _state,
    _revert_version,
    _ProjectState,
)

from cleo.commands.command import Command
from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.event_dispatcher import EventDispatcher
from cleo.events.console_events import COMMAND, SIGNAL, TERMINATE, ERROR
from poetry.console.application import Application
from poetry.plugins.application_plugin import ApplicationPlugin


def _should_apply(command: str) -> bool:
    return command not in ["run", "shell", "dynamic-versioning"]


def _apply_version_via_plugin(application: Application, retain: bool) -> None:
    config = _get_config(application.poetry.pyproject.data)
    name = application.poetry.local_config["name"]
    version = _get_version(config)
    _state.projects[name] = _ProjectState(
        application.poetry.file.path, application.poetry.local_config["version"], version, None,
    )
    application.poetry.package.set_version(version)
    _apply_version(
        version, config, application.poetry.file.path, retain,
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
        _apply_version_via_plugin(self._application, True)
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

        _apply_version_via_plugin(self._application, False)

    def _revert_version(
        self, event: ConsoleCommandEvent, kind: str, dispatcher: EventDispatcher
    ) -> None:
        if not _should_apply(event.command.name):
            return

        _revert_version()
