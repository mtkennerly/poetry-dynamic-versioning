__all__ = []  # type: ignore

import copy
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import textwrap
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, Sequence, Tuple, Union

import jinja2
import tomlkit
import tomlkit.items
from dunamai import (
    bump_version,
    check_version,
    Concern,
    Pattern,
    serialize_pep440,
    serialize_pvp,
    serialize_semver,
    Style,
    Vcs,
    Version,
)

_BYPASS_ENV = "POETRY_DYNAMIC_VERSIONING_BYPASS"
_OVERRIDE_ENV = "POETRY_DYNAMIC_VERSIONING_OVERRIDE"
_DEBUG_ENV = "POETRY_DYNAMIC_VERSIONING_DEBUG"

if sys.version_info >= (3, 8):
    from typing import TypedDict

    _SubstitutionPattern = TypedDict(
        "_SubstitutionPattern",
        {
            "value": str,
            "mode": Optional[str],
        },
    )

    _SubstitutionFolder = TypedDict(
        "_SubstitutionFolder",
        {
            "path": str,
            "files": Optional[Sequence[str]],
            "patterns": Optional[Sequence[Union[str, _SubstitutionPattern]]],
        },
    )

    _Substitution = TypedDict(
        "_Substitution",
        {
            "files": Sequence[str],
            "patterns": Sequence[Union[str, _SubstitutionPattern]],
            "folders": Sequence[_SubstitutionFolder],
        },
    )

    _File = TypedDict(
        "_File",
        {
            "persistent-substitution": Optional[bool],
            "initial-content": Optional[str],
            "initial-content-jinja": Optional[str],
        },
    )

    _JinjaImport = TypedDict(
        "_JinjaImport",
        {
            "module": str,
            "item": Optional[str],
        },
    )

    _FromFile = TypedDict(
        "_FromFile",
        {
            "source": Optional[str],
            "pattern": Optional[str],
        },
    )

    _Config = TypedDict(
        "_Config",
        {
            "enable": bool,
            "vcs": str,
            "dirty": bool,
            "pattern": Optional[str],
            "pattern-prefix": Optional[str],
            "latest-tag": bool,
            "substitution": _Substitution,
            "files": Mapping[str, _File],
            "style": Optional[str],
            "metadata": Optional[bool],
            "format": Optional[str],
            "format-jinja": Optional[str],
            "format-jinja-imports": Sequence[_JinjaImport],
            "bump": bool,
            "tagged-metadata": bool,
            "full-commit": bool,
            "tag-branch": Optional[str],
            "tag-dir": str,
            "strict": bool,
            "fix-shallow-repository": bool,
            "ignore-untracked": bool,
            "from-file": _FromFile,
        },
    )
else:

    class _Config(Mapping):
        pass


class _Mode(Enum):
    Classic = "classic"
    Pep621 = "pep621"


class _ProjectState:
    def __init__(
        self,
        path: Path,
        original_version: Optional[str],
        version: str,
        mode: _Mode,
        dynamic_array: Optional[tomlkit.items.Array],
        substitutions: Optional[MutableMapping[Path, str]] = None,
    ) -> None:
        self.path = path
        self.original_version = original_version
        self.version = version
        self.mode = mode
        self.dynamic_array = dynamic_array
        self.substitutions = {} if substitutions is None else substitutions  # type: MutableMapping[Path, str]


class _State:
    def __init__(self) -> None:
        self.patched_core_poetry_create = False
        self.cli_mode = False
        self.projects = {}  # type: MutableMapping[str, _ProjectState]


_state = _State()


class _SubPattern:
    def __init__(self, value: str, mode: str):
        self.value = value
        self.mode = mode

    @staticmethod
    def from_config(config: Sequence[Union[str, Mapping]]) -> Sequence["_SubPattern"]:
        patterns = []

        for x in config:
            if isinstance(x, str):
                patterns.append(_SubPattern(x, mode="str"))
            else:
                patterns.append(_SubPattern(x["value"], mode=x.get("mode", "str")))

        return patterns


class _FolderConfig:
    def __init__(self, path: Path, files: Sequence[str], patterns: Sequence[_SubPattern]):
        self.path = path
        self.files = files
        self.patterns = patterns

    @staticmethod
    def from_config(config: _Config, root: Path) -> Sequence["_FolderConfig"]:
        files = config["substitution"]["files"]
        patterns = _SubPattern.from_config(config["substitution"]["patterns"])

        main = _FolderConfig(root, files, patterns)
        extra = [
            _FolderConfig(
                root / x["path"],
                x["files"] if x["files"] is not None else files,
                _SubPattern.from_config(x["patterns"]) if x["patterns"] is not None else patterns,
            )
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
                "pattern-prefix": None,
                "latest-tag": False,
                "substitution": {
                    "files": ["*.py", "*/__init__.py", "*/__version__.py", "*/_version.py"],
                    "patterns": [
                        r"(^__version__\s*(?::.*?)?=\s*['\"])[^'\"]*(['\"])",
                        {
                            "value": r"(^__version_tuple__\s*(?::.*?)?=\s*\()[^)]*(\))",
                            "mode": "tuple",
                        },
                    ],
                    "folders": [],
                },
                "files": {},
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
                "strict": False,
                "fix-shallow-repository": False,
                "ignore-untracked": False,
                "from-file": {
                    "source": None,
                    "pattern": None,
                },
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


def _debug(message: str) -> None:
    enabled = os.environ.get(_DEBUG_ENV) == "1"

    if enabled:
        print(message, file=sys.stderr)


def _find_higher_file(*names: str, start: Optional[Path] = None) -> Optional[Path]:
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


def _get_pyproject_path(start: Optional[Path] = None) -> Optional[Path]:
    return _find_higher_file("pyproject.toml", start=start)


def _get_pyproject_path_from_poetry(pyproject) -> Path:
    # poetry-core 1.6.0+:
    recommended = getattr(pyproject, "path", None)
    # poetry-core <1.6.0:
    legacy = getattr(pyproject, "file", None)

    if recommended:
        return recommended
    elif legacy:
        return legacy
    else:
        raise RuntimeError("Unable to determine pyproject.toml path from Poetry instance")


def _get_config(local: Mapping) -> _Config:
    def initialize(data, key):
        if isinstance(data, dict) and key not in data:
            data[key] = None

    if isinstance(local, tomlkit.TOMLDocument):
        local = local.unwrap()

    merged = _deep_merge_dicts(_default_config(), local)["tool"]["poetry-dynamic-versioning"]  # type: _Config

    # Add default values so we don't have to worry about missing keys
    for x in merged["files"].values():
        initialize(x, "initial-content")
        initialize(x, "initial-content-jinja")
        initialize(x, "persistent-substitution")
    for x in merged["format-jinja-imports"]:
        initialize(x, "item")
    for x in merged["substitution"]["folders"]:
        initialize(x, "files")
        initialize(x, "patterns")
    for x in merged["substitution"]["patterns"]:
        initialize(x, "mode")

    return merged


def _get_config_from_path(start: Optional[Path] = None) -> Mapping:
    pyproject_path = _get_pyproject_path(start)
    if pyproject_path is None:
        return _default_config()["tool"]["poetry-dynamic-versioning"]
    pyproject = tomlkit.parse(pyproject_path.read_bytes().decode("utf-8"))
    result = _get_config(pyproject)
    return result


def _validate_config(config: Optional[Mapping] = None) -> Sequence[str]:
    if config is None:
        pyproject_path = _get_pyproject_path()
        if pyproject_path is None:
            raise RuntimeError("Unable to find pyproject.toml")
        config = tomlkit.parse(pyproject_path.read_bytes().decode("utf-8"))

    return _validate_config_section(
        config.get("tool", {}).get("poetry-dynamic-versioning", {}),
        _default_config()["tool"]["poetry-dynamic-versioning"],
        ["tool", "poetry-dynamic-versioning"],
    )


def _validate_config_section(config: Mapping, default: Mapping, path: Sequence[str]) -> Sequence[str]:
    if not default:
        return []

    errors = []

    for (key, value) in config.items():
        if key not in default:
            escaped_key = key if "." not in key else '"{}"'.format(key)
            errors.append("Unknown key: " + ".".join([*path, escaped_key]))
        elif isinstance(value, dict) and isinstance(config.get(key), dict):
            errors.extend(_validate_config_section(config[key], default[key], [*path, key]))

    return errors


def _escape_branch(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return re.sub(r"[^a-zA-Z0-9]", "", value)


def _format_timestamp(value: Optional[dt.datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%Y%m%d%H%M%S")


def _render_jinja(version: Version, template: str, config: _Config, extra: Optional[Mapping] = None) -> str:
    if extra is None:
        extra = {}

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
        **extra,
    }
    custom_context = {}  # type: dict
    for entry in config["format-jinja-imports"]:
        if "module" in entry:
            module = import_module(entry["module"])
            if entry["item"] is not None:
                custom_context[entry["item"]] = getattr(module, entry["item"])
            else:
                custom_context[entry["module"]] = module
    serialized = jinja2.Template(template).render(**default_context, **custom_context)
    return serialized


def _run_cmd(command: str, codes: Sequence[int] = (0,)) -> Tuple[int, str]:
    result = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode().strip()
    if codes and result.returncode not in codes:
        raise RuntimeError("The command '{}' returned code {}. Output:\n{}".format(command, result.returncode, output))
    return (result.returncode, output)


def _get_override_version(name: Optional[str], env: Optional[Mapping] = None) -> Optional[str]:
    env = env if env is not None else os.environ

    if name is not None:
        raw_overrides = env.get(_OVERRIDE_ENV)
        if raw_overrides is not None:
            pairs = raw_overrides.split(",")
            for pair in pairs:
                if "=" not in pair:
                    continue
                k, v = pair.split("=", 1)
                if k.strip() == name:
                    return v.strip()

    bypass = env.get(_BYPASS_ENV)
    if bypass is not None:
        return bypass

    return None


def _get_version_from_file(config: _Config) -> Optional[str]:
    source = config["from-file"]["source"]
    pattern = config["from-file"]["pattern"]

    if source is None:
        return None

    pyproject_path = _get_pyproject_path()
    if pyproject_path is None:
        raise RuntimeError("Unable to find pyproject.toml")

    content = pyproject_path.parent.joinpath(source).read_bytes().decode("utf-8").strip()

    if pattern is None:
        return content

    result = re.search(pattern, content, re.MULTILINE)
    if result is None:
        raise ValueError("File '{}' did not contain a match for '{}'".format(source, pattern))
    return result.group(1)


def _get_version_from_dunamai(
    vcs: Vcs, pattern: Union[str, Pattern], config: _Config, *, strict: Optional[bool] = None
) -> Version:
    return Version.from_vcs(
        vcs=vcs,
        pattern=pattern,
        latest_tag=config["latest-tag"],
        tag_dir=config["tag-dir"],
        tag_branch=config["tag-branch"],
        full_commit=config["full-commit"],
        strict=config["strict"] if strict is None else strict,
        pattern_prefix=config["pattern-prefix"],
        ignore_untracked=config["ignore-untracked"],
    )


def _get_version(config: _Config, name: Optional[str] = None) -> Tuple[str, Version]:
    override = _get_override_version(name)
    if override is not None:
        return (override, Version.parse(override))

    override = _get_version_from_file(config)
    if override is not None:
        return (override, Version.parse(override))

    vcs = Vcs(config["vcs"])
    style = Style(config["style"]) if config["style"] is not None else None

    pattern = config["pattern"] if config["pattern"] is not None else Pattern.Default  # type: Union[str, Pattern]

    if config["fix-shallow-repository"]:
        # We start without strict so we can inspect the concerns.
        version = _get_version_from_dunamai(vcs, pattern, config, strict=False)
        retry = config["strict"]

        if Concern.ShallowRepository in version.concerns and version.vcs == Vcs.Git:
            retry = True
            _run_cmd("git fetch --unshallow")

        if retry:
            version = _get_version_from_dunamai(vcs, pattern, config)
    else:
        version = _get_version_from_dunamai(vcs, pattern, config)

    for concern in version.concerns:
        print("Warning: {}".format(concern.message()), file=sys.stderr)

    if config["format-jinja"]:
        serialized = _render_jinja(version, config["format-jinja"], config)
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

    return (serialized, version)


def _substitute_version(name: str, version: str, folders: Sequence[_FolderConfig]) -> None:
    if _state.projects[name].substitutions:
        # Already ran; don't need to repeat.
        return

    files = {}  # type: MutableMapping[Path, _FolderConfig]
    for folder in folders:
        for file_glob in folder.files:
            i = 0

            # call str() since file_glob here could be a non-internable string
            for match in folder.path.glob(str(file_glob)):
                i += 1
                resolved = match.resolve()
                if resolved in files:
                    continue
                files[resolved] = folder

            if i == 0:
                _debug("No files found for substitution with glob '{}' in folder '{}'".format(file_glob, folder.path))

    for file, config in files.items():
        original_content = file.read_bytes().decode("utf-8")
        new_content = _substitute_version_in_text(version, original_content, config.patterns)
        if original_content != new_content:
            _state.projects[name].substitutions[file] = original_content
            file.write_bytes(new_content.encode("utf-8"))
        else:
            _debug("No changes made during substitution in file '{}'".format(file))


def _substitute_version_in_text(version: str, content: str, patterns: Sequence[_SubPattern]) -> str:
    new_content = content

    for pattern in patterns:
        if pattern.mode == "str":
            insert = version
        elif pattern.mode == "tuple":
            parts = []
            split = version.split("+", 1)
            split = [*re.split(r"[-.]", split[0]), *split[1:]]
            for part in split:
                if part == "":
                    continue
                try:
                    parts.append(str(int(part)))
                except ValueError:
                    parts.append('"{}"'.format(part))
            insert = ", ".join(parts)
            if len(parts) == 1:
                insert += ","
        else:
            raise ValueError("Invalid substitution mode: {}".format(pattern.mode))

        new_content = re.sub(pattern.value, r"\g<1>{}\g<2>".format(insert), new_content, flags=re.MULTILINE)

    return new_content


def _apply_version(
    name: str,
    version: str,
    instance: Version,
    config: _Config,
    pyproject_path: Path,
    mode: _Mode,
    retain: bool = False,
) -> None:
    pyproject = tomlkit.parse(pyproject_path.read_bytes().decode("utf-8"))

    if mode == _Mode.Classic:
        pyproject["tool"]["poetry"]["version"] = version  # type: ignore
    elif mode == _Mode.Pep621:
        pyproject["project"]["dynamic"].remove("version")  # type: ignore
        pyproject["project"]["version"] = version  # type: ignore
        pyproject["tool"]["poetry"].pop("version")  # type: ignore

    # Disable the plugin in case we're building a source distribution,
    # which won't have access to the VCS info at install time.
    # We revert this later when we deactivate.
    if not retain and not _state.cli_mode:
        pyproject["tool"]["poetry-dynamic-versioning"]["enable"] = False  # type: ignore

    pyproject_path.write_bytes(tomlkit.dumps(pyproject).encode("utf-8"))

    for file_name, file_info in config["files"].items():
        full_file = pyproject_path.parent.joinpath(file_name)

        if file_info["initial-content-jinja"] is not None:
            if not full_file.parent.exists():
                full_file.parent.mkdir()
            initial = textwrap.dedent(
                _render_jinja(
                    instance,
                    file_info["initial-content-jinja"],
                    config,
                    {"formatted_version": version},
                )
            )
            full_file.write_bytes(initial.encode("utf-8"))
        elif file_info["initial-content"] is not None:
            if not full_file.parent.exists():
                full_file.parent.mkdir()
            initial = textwrap.dedent(file_info["initial-content"])
            full_file.write_bytes(initial.encode("utf-8"))

    _substitute_version(
        name,  # type: ignore
        version,
        _FolderConfig.from_config(config, pyproject_path.parent),
    )


def _get_and_apply_version(
    pyproject_path: Optional[Path] = None,
    retain: bool = False,
    force: bool = False,
    io: bool = True,
) -> Optional[str]:
    if pyproject_path is None:
        pyproject_path = _get_pyproject_path()
        if pyproject_path is None:
            raise RuntimeError("Unable to find pyproject.toml")

    # The actual type is `tomlkit.TOMLDocument`, which is important to preserve formatting,
    # but it also causes a lot of type-checking noise.
    pyproject = tomlkit.parse(pyproject_path.read_bytes().decode("utf-8"))  # type: Mapping

    classic = "tool" in pyproject and "poetry" in pyproject["tool"] and "name" in pyproject["tool"]["poetry"]
    pep621 = (
        "project" in pyproject
        and "name" in pyproject["project"]
        and "dynamic" in pyproject["project"]
        and "version" in pyproject["project"]["dynamic"]
        and "version" not in pyproject["project"]
        and "tool" in pyproject
        and "poetry" in pyproject["tool"]
        and "version" in pyproject["tool"]["poetry"]
    )

    if classic:
        name = pyproject["tool"]["poetry"]["name"]
        original = pyproject["tool"]["poetry"]["version"]
        dynamic_array = None
    elif pep621:
        name = pyproject["project"]["name"]
        original = pyproject["tool"]["poetry"]["version"]
        dynamic_array = pyproject["project"]["dynamic"]
    else:
        return None

    if name in _state.projects:
        return name

    config = _get_config(pyproject)
    if not config["enable"] and not force:
        return name if name in _state.projects else None

    initial_dir = Path.cwd()
    target_dir = pyproject_path.parent
    os.chdir(str(target_dir))
    try:
        version, instance = _get_version(config, name)
    finally:
        os.chdir(str(initial_dir))

    if classic and name is not None and original is not None:
        mode = _Mode.Classic
        _state.projects[name] = _ProjectState(pyproject_path, original, version, mode, dynamic_array)
        if io:
            _apply_version(name, version, instance, config, pyproject_path, mode, retain)
    elif pep621 and name is not None:
        mode = _Mode.Pep621
        _state.projects[name] = _ProjectState(pyproject_path, original, version, mode, dynamic_array)
        if io:
            _apply_version(name, version, instance, config, pyproject_path, mode, retain)

    return name


def _revert_version(retain: bool = False) -> None:
    for project, state in _state.projects.items():
        pyproject = tomlkit.parse(state.path.read_bytes().decode("utf-8"))

        if state.substitutions:
            config = _get_config(pyproject)

            persistent = []
            for file, file_info in config["files"].items():
                if file_info["persistent-substitution"]:
                    persistent.append(state.path.parent.joinpath(file))

            for file, content in state.substitutions.items():
                if file in persistent:
                    continue

                file.write_bytes(content.encode("utf-8"))

            # Reread pyproject.toml in case the substitutions affected it.
            pyproject = tomlkit.parse(state.path.read_bytes().decode("utf-8"))

        if state.mode == _Mode.Classic:
            if state.original_version is not None:
                pyproject["tool"]["poetry"]["version"] = state.original_version  # type: ignore
        elif state.mode == _Mode.Pep621:
            if state.dynamic_array is not None:
                pyproject["project"]["dynamic"] = state.dynamic_array
            if "version" in pyproject["project"]:  # type: ignore
                pyproject["project"].pop("version")  # type: ignore
            if state.original_version is not None:
                pyproject["tool"]["poetry"]["version"] = state.original_version  # type: ignore

        if not retain and not _state.cli_mode:
            pyproject["tool"]["poetry-dynamic-versioning"]["enable"] = True  # type: ignore

        state.path.write_bytes(tomlkit.dumps(pyproject).encode("utf-8"))

    _state.projects.clear()
