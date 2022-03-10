__all__ = []  # type: ignore

import copy
import datetime as dt
import os
import re
from importlib import import_module
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, Sequence

import tomlkit

_VERSION_PATTERN = r"""
    (?x)                                                (?# ignore whitespace)
    ^v(?P<base>\d+(\.\d+)*)                             (?# v1.2.3)
    (-?((?P<stage>[a-zA-Z]+)\.?(?P<revision>\d+)?))?    (?# b0)
    (\+(?P<tagged_metadata>.+))?$                       (?# +linux)
""".strip()

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
    def __init__(
        self,
        projects: MutableMapping[str, _ProjectState] = None,
    ) -> None:
        if projects is None:
            self.projects = {}  # type: MutableMapping[str, _ProjectState]
        else:
            self.projects = projects


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
                    "patterns": [r"(^__version__\s*(?::.*?)?=\s*['\"])[^'\"]*(['\"])"],
                },
                "style": None,
                "metadata": None,
                "format": None,
                "format-jinja": None,
                "format-jinja-imports": [],
                "bump": False,
                "tagged-metadata": False,
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


def _get_config(local: Mapping) -> Mapping:
    return _deep_merge_dicts(_default_config(), local)["tool"]["poetry-dynamic-versioning"]


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

    version = Version.from_vcs(
        vcs, config["pattern"], config["latest-tag"], config["subversion"]["tag-dir"]
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
            bump=config["bump"] and version.distance > 0,
            tagged_metadata=config["tagged-metadata"],
        )

    return serialized


def _substitute_version(
    name: str, root: Path, file_globs: Sequence[str], patterns: Sequence[str], version: str
) -> None:
    if _state.projects[name].substitutions:
        # Already ran; don't need to repeat.
        return

    files = set()
    for file_glob in file_globs:
        # since file_glob here could be a non-internable string
        for match in root.glob(str(file_glob)):
            files.add(match.resolve())
    for file in files:
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
) -> str:
    pyproject = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))
    if pyproject["tool"]["poetry"]["version"] != version:
        pyproject["tool"]["poetry"]["version"] = version

        # Disable the plugin in case we're building a source distribution,
        # which won't have access to the VCS info at install time.
        # We revert this later when we deactivate.
        if not retain:
            pyproject["tool"]["poetry-dynamic-versioning"]["enable"] = False

        pyproject_path.write_text(tomlkit.dumps(pyproject), encoding="utf-8")

    name = pyproject["tool"]["poetry"]["name"]

    _substitute_version(
        name,
        pyproject_path.parent,
        config["substitution"]["files"],
        config["substitution"]["patterns"],
        version,
    )

    return name


def _revert_version(retain: bool = False) -> None:
    for project, state in _state.projects.items():
        if state.original_version != state.version:
            pyproject = tomlkit.parse(state.path.read_text(encoding="utf-8"))
            pyproject["tool"]["poetry"]["version"] = state.original_version

            if not retain:
                pyproject["tool"]["poetry-dynamic-versioning"]["enable"] = True

            state.path.write_text(tomlkit.dumps(pyproject), encoding="utf-8")

        if state.substitutions:
            for file, content in state.substitutions.items():
                file.write_text(content, encoding="utf-8")

    _state.projects.clear()
