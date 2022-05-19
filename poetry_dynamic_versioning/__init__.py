__all__ = []  # type: ignore

import builtins
import copy
import datetime as dt
import os
import re
from importlib import import_module
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, Sequence

import tomlkit

_BYPASS_ENV = "POETRY_DYNAMIC_VERSIONING_BYPASS"


class _ProjectState:
    def __init__(
        self,
        path: Path,
        original_version: str,
        version: str,
        substitutions: MutableMapping[Path, str] = None,
    ) -> None:
        self.path = path
        self.original_version = original_version
        self.version = version
        self.substitutions = {} if substitutions is None else substitutions


class _State:
    def __init__(self) -> None:
        self.patched_poetry_create = False
        self.patched_core_poetry_create = False
        self.patched_poetry_command_run = False
        self.patched_poetry_command_shell = False
        self.original_import_func = builtins.__import__
        self.cli_mode = False
        self.projects = {}  # type: MutableMapping[str, _ProjectState]


_state = _State()


class _FolderConfig:
    def __init__(self, path: Path, files: Sequence[str], patterns: Sequence[str]):
        self.path = path
        self.files = files
        self.patterns = patterns

    @staticmethod
    def from_config(config: Mapping, root: Path) -> Sequence["_FolderConfig"]:
        files = config["substitution"]["files"]
        patterns = config["substitution"]["patterns"]

        main = _FolderConfig(root, files, patterns)
        extra = [
            _FolderConfig(root / x["path"], x.get("files", files), x.get("patterns", patterns))
            for x in config["substitution"]["folders"]
        ]

        return [main, *extra]


def _default_config() -> Mapping:
    return {
        "tool": {
            "poetry-dynamic-versioning": {
                "enable": False,
                "vcs": "any",
                "dirty": False,
                "pattern": None,
                "latest-tag": False,
                "substitution": {
                    "files": ["*.py", "*/__init__.py", "*/__version__.py", "*/_version.py"],
                    "patterns": [r"(^__version__\s*(?::.*?)?=\s*['\"])[^'\"]*(['\"])"],
                    "folders": [],
                },
                "style": None,
                "metadata": None,
                "format": None,
                "format-jinja": None,
                "format-jinja-imports": [],
                "bump": False,
                "tagged-metadata": False,
                "full-commit": False,
                "tag-branch": None,
                "tag-dir": "tags",
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
    # Note: We need to make sure we get a pathlib object. Many tox poetry
    # helpers will pass us a string and not a pathlib object. See issue #40.
    if start is None:
        start = Path.cwd()
    elif not isinstance(start, Path):
        start = Path(start)
    for level in [start, *start.parents]:
        for name in names:
            if (level / name).is_file():
                return level / name
    return None


def _get_pyproject_path(start: Path = None) -> Optional[Path]:
    return _find_higher_file("pyproject.toml", start=start)


def _get_config(local: Mapping) -> Mapping:
    return _deep_merge_dicts(_default_config(), local)["tool"]["poetry-dynamic-versioning"]


def _get_config_from_path(start: Path = None) -> Mapping:
    pyproject_path = _get_pyproject_path(start)
    if pyproject_path is None:
        return _default_config()["tool"]["poetry-dynamic-versioning"]
    pyproject = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))
    result = _get_config(pyproject)
    return result


def _escape_branch(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return re.sub(r"[^a-zA-Z0-9]", "", value)


def _format_timestamp(value: Optional[dt.datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%Y%m%d%H%M%S")


def _get_version(config: Mapping) -> str:
    bypass = os.environ.get(_BYPASS_ENV)
    if bypass is not None:
        return bypass

    import jinja2
    from dunamai import (
        bump_version,
        check_version,
        Pattern,
        serialize_pep440,
        serialize_pvp,
        serialize_semver,
        Style,
        Vcs,
        Version,
    )

    vcs = Vcs(config["vcs"])
    style = config["style"]
    if style is not None:
        style = Style(style)

    pattern = config["pattern"] if config["pattern"] is not None else Pattern.Default

    version = Version.from_vcs(
        vcs,
        pattern,
        config["latest-tag"],
        config["tag-dir"],
        config["tag-branch"],
        config["full-commit"],
    )

    if config["format-jinja"]:
        if config["bump"] and version.distance > 0:
            version = version.bump()
        default_context = {
            "base": version.base,
            "version": version,
            "stage": version.stage,
            "revision": version.revision,
            "distance": version.distance,
            "commit": version.commit,
            "dirty": version.dirty,
            "branch": version.branch,
            "branch_escaped": _escape_branch(version.branch),
            "timestamp": _format_timestamp(version.timestamp),
            "env": os.environ,
            "bump_version": bump_version,
            "tagged_metadata": version.tagged_metadata,
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
        serialized = version.serialize(
            metadata=config["metadata"],
            dirty=config["dirty"],
            format=config["format"],
            style=style,
            bump=config["bump"],
            tagged_metadata=config["tagged-metadata"],
        )

    return serialized


def _substitute_version(name: str, version: str, folders: Sequence[_FolderConfig]) -> None:
    if _state.projects[name].substitutions:
        # Already ran; don't need to repeat.
        return

    files = {}  # type: MutableMapping[Path, Sequence[str]]
    for folder in folders:
        for file_glob in folder.files:
            # call str() since file_glob here could be a non-internable string
            for match in folder.path.glob(str(file_glob)):
                resolved = match.resolve()
                if resolved in files:
                    continue
                files[resolved] = folder.patterns

    for file, patterns in files.items():
        original_content = file.read_text(encoding="utf-8")
        new_content = original_content
        for pattern in patterns:
            new_content = re.sub(
                pattern, r"\g<1>{}\g<2>".format(version), new_content, flags=re.MULTILINE
            )
        if original_content != new_content:
            _state.projects[name].substitutions[file] = original_content
            file.write_text(new_content, encoding="utf-8")


def _apply_version(
    version: str, config: Mapping, pyproject_path: Path, retain: bool = False
) -> None:
    pyproject = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))

    if pyproject["tool"]["poetry"]["version"] != version:  # type: ignore
        pyproject["tool"]["poetry"]["version"] = version  # type: ignore

        # Disable the plugin in case we're building a source distribution,
        # which won't have access to the VCS info at install time.
        # We revert this later when we deactivate.
        if not retain and not _state.cli_mode:
            pyproject["tool"]["poetry-dynamic-versioning"]["enable"] = False  # type: ignore

        pyproject_path.write_text(tomlkit.dumps(pyproject), encoding="utf-8")

    name = pyproject["tool"]["poetry"]["name"]  # type: ignore

    _substitute_version(
        name,  # type: ignore
        version,
        _FolderConfig.from_config(config, pyproject_path.parent),
    )


def _get_and_apply_version(
    name: Optional[str] = None,
    original: Optional[str] = None,
    pyproject: Optional[Mapping] = None,
    pyproject_path: Optional[Path] = None,
    cd: bool = False,
    retain: bool = False,
    # fmt: off
    force: bool = False
    # fmt: on
) -> Optional[str]:
    if name is not None and name in _state.projects:
        return name

    if pyproject_path is None:
        pyproject_path = _get_pyproject_path()
        if pyproject_path is None:
            raise RuntimeError("Unable to find pyproject.toml")

    if pyproject is None:
        pyproject = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))

    if name is None or original is None:
        name = pyproject["tool"]["poetry"]["name"]
        original = pyproject["tool"]["poetry"]["version"]
        if name in _state.projects:
            return name

    config = _get_config(pyproject)
    if not config["enable"] and not force:
        return name if name in _state.projects else None

    initial_dir = Path.cwd()
    target_dir = pyproject_path.parent
    if cd:
        os.chdir(str(target_dir))
    try:
        version = _get_version(config)
    finally:
        if cd:
            os.chdir(str(initial_dir))

    # Condition will always be true, but it makes Mypy happy.
    if name is not None and original is not None:
        _state.projects[name] = _ProjectState(pyproject_path, original, version)
        _apply_version(version, config, pyproject_path, retain)

    return name


def _revert_version(retain: bool = False) -> None:
    for project, state in _state.projects.items():
        if state.original_version != state.version:
            pyproject = tomlkit.parse(state.path.read_text(encoding="utf-8"))
            pyproject["tool"]["poetry"]["version"] = state.original_version  # type: ignore

            if not retain and not _state.cli_mode:
                pyproject["tool"]["poetry-dynamic-versioning"]["enable"] = True  # type: ignore

            state.path.write_text(tomlkit.dumps(pyproject), encoding="utf-8")

        if state.substitutions:
            for file, content in state.substitutions.items():
                file.write_text(content, encoding="utf-8")

    _state.projects.clear()
