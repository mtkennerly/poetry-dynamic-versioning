__all__ = [
    "DynamicVersioningCommand",
    "DynamicVersioningPlugin",
]

import functools
import os

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
    cli,
    _get_config,
    _get_and_apply_version,
    _get_pyproject_path_from_poetry,
    _state,
    _revert_version,
)

_COMMAND_ENV = "POETRY_DYNAMIC_VERSIONING_COMMANDS"
_COMMAND_NO_IO_ENV = "POETRY_DYNAMIC_VERSIONING_COMMANDS_NO_IO"


def _patch_dependency_versions(io: bool) -> None:
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
        _apply_version_via_plugin(instance, io=io)
        return instance

    Factory.create_poetry = patched_create_poetry
    _state.patched_core_poetry_create = True


def _should_apply(command: str) -> bool:
    override = os.environ.get(_COMMAND_ENV)
    if override is not None:
        return command in override.split(",")
    else:
        return command not in ["run", "shell", cli.Command.dv, cli.Command.dv_enable, cli.Command.dv_show]


def _should_apply_with_io(command: str) -> bool:
    override = os.environ.get(_COMMAND_NO_IO_ENV)
    if override is not None:
        return command not in override.split(",")
    else:
        return command not in ["version"]


def _apply_version_via_plugin(
    poetry: Poetry,
    retain: bool = False,
    force: bool = False,
    standalone: bool = False,
    # fmt: off
    io: bool = True
    # fmt: on
) -> None:
    name = _get_and_apply_version(
        pyproject_path=_get_pyproject_path_from_poetry(poetry.pyproject),
        retain=retain,
        force=force,
        io=io,
    )
    if name:
        version = _state.projects[name].version

        # Would be nice to use `.set_version()`, but it's only available on
        # Poetry's `ProjectPackage`, not poetry-core's `ProjectPackage`.
        poetry._package._version = PoetryCoreVersion.parse(version)
        poetry._package._pretty_version = version

        if standalone:
            cli.report_apply(name)


class DynamicVersioningCommand(Command):
    name = cli.Command.dv
    description = cli.Help.main

    def __init__(self, application: Application):
        super().__init__()
        self._application = application

    def handle(self) -> int:
        _state.cli_mode = True
        _apply_version_via_plugin(self._application.poetry, retain=True, force=True, standalone=True)
        return 0


class DynamicVersioningEnableCommand(Command):
    name = cli.Command.dv_enable
    description = cli.Help.enable

    def __init__(self, application: Application):
        super().__init__()
        self._application = application

    def handle(self) -> int:
        _state.cli_mode = True
        cli.enable()
        return 0


class DynamicVersioningShowCommand(Command):
    name = cli.Command.dv_show
    description = cli.Help.show

    def __init__(self, application: Application):
        super().__init__()
        self._application = application

    def handle(self) -> int:
        _state.cli_mode = True
        cli.show()
        return 0


class DynamicVersioningPlugin(ApplicationPlugin):
    def __init__(self):
        self._application = None

    def activate(self, application: Application) -> None:
        self._application = application

        application.command_loader.register_factory(cli.Command.dv, lambda: DynamicVersioningCommand(application))
        application.command_loader.register_factory(
            cli.Command.dv_enable, lambda: DynamicVersioningEnableCommand(application)
        )
        application.command_loader.register_factory(
            cli.Command.dv_show, lambda: DynamicVersioningShowCommand(application)
        )

        try:
            local = self._application.poetry.pyproject.data
        except RuntimeError:
            # We're not in a Poetry project directory
            return

        cli.validate(standalone=False, config=local)

        config = _get_config(local)
        if not config["enable"]:
            return

        application.event_dispatcher.add_listener(COMMAND, self._apply_version)
        application.event_dispatcher.add_listener(SIGNAL, self._revert_version)
        application.event_dispatcher.add_listener(TERMINATE, self._revert_version)
        application.event_dispatcher.add_listener(ERROR, self._revert_version)

    def _apply_version(self, event: ConsoleCommandEvent, kind: str, dispatcher: EventDispatcher) -> None:
        if not _should_apply(event.command.name):
            return

        io = _should_apply_with_io(event.command.name)

        _apply_version_via_plugin(self._application.poetry, io=io)
        _patch_dependency_versions(io)

    def _revert_version(self, event: ConsoleCommandEvent, kind: str, dispatcher: EventDispatcher) -> None:
        if not _should_apply(event.command.name):
            return

        if not _should_apply_with_io(event.command.name):
            return

        _revert_version()
