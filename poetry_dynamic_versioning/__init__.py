__all__ = ["activate", "deactivate", "get_config"]

import atexit
import builtins
import copy
import functools
import jinja2
import os
import re
from importlib import import_module
from pathlib import Path
from typing import Mapping, MutableMapping, MutableSet, Optional, Sequence, Tuple

import tomlkit
from dunamai import (
    bump_version,
    check_version,
    serialize_pep440,
    serialize_pvp,
    serialize_semver,
    Style,
    Vcs,
    Version,
)

_VERSION_PATTERN = r"^v(?P<base>\d+\.\d+\.\d+)(-?((?P<stage>[a-zA-Z]+)\.?(?P<revision>\d+)?))?$"
_PDV_START_DIR = "POETRY_DYNAMIC_VERSIONING_START_DIR"


class _State:
    def __init__(
        self,
        patched_poetry_create: bool = False,
        patched_poetry_command_run: bool = False,
        original_version: str = None,
        version: Tuple[Version, str] = None,
        substitutions: MutableMapping[Path, str] = None,
        cli_mode: bool = False,
    ) -> None:
        self.patched_poetry_create = patched_poetry_create
        self.patched_poetry_command_run = patched_poetry_command_run
        self.original_version = original_version
        self.version = version
        self.original_import_func = builtins.__import__
        self.substitutions = {} if substitutions is None else substitutions
        self.cli_mode = cli_mode


_state = _State()


def _default_config() -> Mapping:
    return {
        "tool": {
            "poetry-dynamic-versioning": {
                "enable": False,
                "vcs": "any",
                "dirty": False,
                "pattern": _VERSION_PATTERN,
                "latest-tag": False,
                "subversion": {"tag-dir": "tags"},
                "substitution": {
                    "files": ["*.py", "*/__init__.py", "*/__version__.py", "*/_version.py"],
                    "patterns": [r"(^__version__\s*=\s*['\"])[^'\"]*(['\"])"],
                },
                "style": None,
                "metadata": None,
                "format": None,
                "format-jinja": None,
                "format-jinja-imports": [],
            }
        }
    }


def _deep_merge_dicts(base: Mapping, addition: Mapping) -> Mapping:
    result = dict(copy.deepcopy(base))
    for key, value in addition.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            result[key] = _deep_merge_dicts(base[key], value)
        else:
            result[key] = value
    return result


def _find_higher_file(*names: str, start: Path = None) -> Optional[Path]:
    if start is None:
        start = Path.cwd()
    for level in [start, *start.parents]:
        for name in names:
            if (level / name).is_file():
                return level / name
    return None


def _get_pyproject_path(start: Path = None) -> Optional[Path]:
    return _find_higher_file("pyproject.toml", start=start)


def get_config(start: Path = None) -> Mapping:
    pyproject_path = _get_pyproject_path(start)
    if pyproject_path is None:
        return _default_config()["tool"]["poetry-dynamic-versioning"]
    pyproject = tomlkit.parse(pyproject_path.read_text())
    result = _deep_merge_dicts(_default_config(), pyproject)["tool"]["poetry-dynamic-versioning"]
    return result


def _get_version(config: Mapping) -> Tuple[Version, str]:
    vcs = Vcs(config["vcs"])
    style = config["style"]
    if style is not None:
        style = Style(style)

    version = Version.from_vcs(
        vcs, config["pattern"], config["latest-tag"], config["subversion"]["tag-dir"]
    )
    if config["format-jinja"]:
        default_context = {
            "base": version.base,
            "stage": version.stage,
            "revision": version.revision,
            "distance": version.distance,
            "commit": version.commit,
            "dirty": version.dirty,
            "env": os.environ,
            "bump_version": bump_version,
            "serialize_pep440": serialize_pep440,
            "serialize_pvp": serialize_pvp,
            "serialize_semver": serialize_semver,
        }
        custom_context = {}  # type: dict
        for entry in config["format-jinja-imports"]:
            if "module" in entry:
                module = import_module(entry["module"])
                if "item" in entry:
                    custom_context[entry["item"]] = getattr(module, entry["item"])
                else:
                    custom_context[entry["module"]] = module
        serialized = jinja2.Template(config["format-jinja"]).render(
            **default_context, **custom_context
        )
        if style is not None:
            check_version(serialized, style)
    else:
        serialized = version.serialize(config["metadata"], config["dirty"], config["format"], style)

    return (version, serialized)


def _substitute_version(
    root: Path, file_globs: Sequence[str], patterns: Sequence[str], version: str
) -> None:
    if _state.substitutions:
        # Already ran; don't need to repeat.
        return

    files = set()  # type: MutableSet[Path]
    for file_glob in file_globs:
        # since file_glob here could be a non-internable string
        for match in root.glob(str(file_glob)):
            files.add(match.resolve())
    for file in files:
        original_content = file.read_text()
        new_content = original_content
        for pattern in patterns:
            new_content = re.sub(
                pattern, r"\g<1>{}\g<2>".format(version), new_content, flags=re.MULTILINE
            )
        if original_content != new_content:
            _state.substitutions[file] = original_content
            file.write_text(new_content)


def _apply_version(version: str, config: Mapping, pyproject_path: Path) -> None:
    pyproject = tomlkit.parse(pyproject_path.read_text())
    if pyproject["tool"]["poetry"]["version"] != version:
        pyproject["tool"]["poetry"]["version"] = version
        pyproject_path.write_text(tomlkit.dumps(pyproject))

    _substitute_version(
        pyproject_path.parent,
        config["substitution"]["files"],
        config["substitution"]["patterns"],
        version,
    )


def _revert_version() -> None:
    if _state.original_version and _state.version and _state.original_version != _state.version[1]:
        pyproject_path = _get_pyproject_path()
        if pyproject_path is None:
            return
        pyproject = tomlkit.parse(pyproject_path.read_text())
        pyproject["tool"]["poetry"]["version"] = _state.original_version
        pyproject_path.write_text(tomlkit.dumps(pyproject))
        _state.original_version = None

    if _state.substitutions:
        for file, content in _state.substitutions.items():
            file.write_text(content)
        _state.substitutions.clear()


def _enable_cli_mode() -> None:
    _state.cli_mode = True


def _patch_poetry_create(factory_mod) -> None:
    original_poetry_create = getattr(factory_mod, "Factory").create_poetry

    poetry_version_module = _state.original_import_func(
        "poetry.semver.version", fromlist=["Version"]
    )

    pyproject_path = _get_pyproject_path()
    if pyproject_path is None:
        raise RuntimeError("Unable to find pyproject.toml")
    config = get_config()

    @functools.wraps(original_poetry_create)
    def alt_poetry_create(cls, *args, **kwargs):
        instance = original_poetry_create(cls, *args, **kwargs)

        if not _state.cli_mode:
            first_time = _state.version is None
            if first_time:
                current_dir = Path.cwd()
                os.chdir(os.environ[_PDV_START_DIR])
                try:
                    _state.version = _get_version(config)
                finally:
                    os.chdir(str(current_dir))

            dynamic_version = _state.version[1]
            if first_time:
                pyproject = tomlkit.parse(pyproject_path.read_text())
                if not _state.original_version:
                    _state.original_version = pyproject["tool"]["poetry"]["version"]
                _apply_version(dynamic_version, config, pyproject_path)

            instance._package._version = poetry_version_module.Version.parse(dynamic_version)
            instance._package._pretty_version = dynamic_version

        return instance

    getattr(factory_mod, "Factory").create_poetry = alt_poetry_create


def _patch_poetry_command_run(run_mod) -> None:
    original_poetry_command_run = getattr(run_mod, "RunCommand").handle

    @functools.wraps(original_poetry_command_run)
    def alt_poetry_command_run(self, *args, **kwargs):
        # As of version 1.0.0b2, on Linux, the `poetry run` command
        # uses `os.execvp` function instead of spawning a new process.
        # This prevents the atexit `deactivate` hook to be invoked.
        # For this reason, we immediately call `deactivate` before
        # actually executing the run command.
        deactivate()
        return original_poetry_command_run(self, *args, **kwargs)

    getattr(run_mod, "RunCommand").handle = alt_poetry_command_run


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
            if name == "poetry.factory" and fromlist:
                _patch_poetry_create(module)
                _state.patched_poetry_create = True
            elif name == "poetry" and "factory" in fromlist:
                _patch_poetry_create(module.factory)
                _state.patched_poetry_create = True

        if not _state.patched_poetry_command_run:
            if name == "poetry.console.commands.run" and fromlist:
                _patch_poetry_command_run(module)
                _state.patched_poetry_command_run = True
            elif name == "poetry.console.commands" and "run" in fromlist:
                _patch_poetry_command_run(module.run)
                _state.patched_poetry_command_run = True

        return module

    builtins.__import__ = alt_import


def _apply_patches() -> None:
    try:
        # Use the least invasive patching if possible.
        if not _state.patched_poetry_create:
            from poetry import factory as factory_mod

            _patch_poetry_create(factory_mod)
            _state.patched_poetry_create = True
        if not _state.patched_poetry_command_run:
            from poetry.console.commands import run as run_mod

            _patch_poetry_command_run(run_mod)
            _state.patched_poetry_command_run = True
    except ImportError:
        # Otherwise, wait until Poetry is available to be patched.
        _patch_builtins_import()


def activate() -> None:
    config = get_config()
    if not config["enable"]:
        return

    if _PDV_START_DIR not in os.environ:
        # This is needed for Pip's PEP 517 isolated builds,
        # so we can briefly switch back to the original directory.
        # It builds in a temporary directory, and it also launches
        # multiple processes, so we can't just put this in State.
        os.environ[_PDV_START_DIR] = str(Path.cwd())

    _apply_patches()
    atexit.register(deactivate)


def deactivate() -> None:
    if not _state.cli_mode:
        _revert_version()
