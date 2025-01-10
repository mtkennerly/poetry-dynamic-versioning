import argparse
import sys
from typing import (
    Mapping,
    Optional,
)

import tomlkit

from poetry_dynamic_versioning import (
    _get_and_apply_version,
    _get_config,
    _get_pyproject_path,
    _get_version,
    _state,
    _validate_config,
)

_DEFAULT_REQUIRES = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]
_DEFAULT_BUILD_BACKEND = "poetry_dynamic_versioning.backend"


class Key:
    tool = "tool"
    pdv = "poetry-dynamic-versioning"
    enable = "enable"
    build_system = "build-system"
    requires = "requires"
    build_backend = "build-backend"
    project = "project"
    poetry = "poetry"
    dynamic = "dynamic"
    version = "version"


class Command:
    dv = "dynamic-versioning"
    enable = "enable"
    show = "show"
    dv_enable = "{} {}".format(dv, enable)
    dv_show = "{} {}".format(dv, show)


class Help:
    main = (
        "Apply the dynamic version to all relevant files and leave the changes in-place."
        " This allows you to activate the plugin behavior on demand and inspect the result."
        " Your configuration will be detected from pyproject.toml as normal."
    )
    enable = (
        "Update pyproject.toml to enable the plugin using a typical configuration."
        " The output may not be suitable for more complex use cases."
    )
    show = "Print the version without changing any files."


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=Help.main)

    subparsers = parser.add_subparsers(dest="cmd", title="subcommands")
    subparsers.add_parser(Command.enable, help=Help.enable)
    subparsers.add_parser(Command.show, help=Help.show)

    return parser


def parse_args(argv=None) -> argparse.Namespace:
    return get_parser().parse_args(argv)


def validate(*, standalone: bool, config: Optional[Mapping] = None) -> None:
    errors = _validate_config(config)
    if errors:
        if standalone:
            print("Configuration issues:", file=sys.stderr)
        else:
            print("poetry-dynamic-versioning configuration issues:", file=sys.stderr)
        for error in errors:
            print("  - {}".format(error), file=sys.stderr)


def apply(*, standalone: bool) -> None:
    validate(standalone=standalone)

    name = _get_and_apply_version(retain=True, force=True)
    if not name:
        raise RuntimeError("Unable to determine a dynamic version")

    if standalone:
        report_apply(name)


def report_apply(name: str) -> None:
    print("Version: {}".format(_state.projects[name].version), file=sys.stderr)
    if _state.projects[name].substitutions:
        print("Files with substitutions:", file=sys.stderr)
        for file_name in _state.projects[name].substitutions:
            print("  - {}".format(file_name), file=sys.stderr)
    else:
        print("Files with substitutions: none", file=sys.stderr)


def enable() -> None:
    pyproject_path = _get_pyproject_path()
    if pyproject_path is None:
        raise RuntimeError("Unable to find pyproject.toml")
    config = tomlkit.parse(pyproject_path.read_bytes().decode("utf-8"))

    config = _enable_in_doc(config)
    pyproject_path.write_bytes(tomlkit.dumps(config).encode("utf-8"))


def _enable_in_doc(doc: tomlkit.TOMLDocument) -> tomlkit.TOMLDocument:
    pdv_table = tomlkit.table().add(Key.enable, True)
    tool_table = tomlkit.table().add(Key.pdv, pdv_table)

    if doc.get(Key.tool) is None:
        doc[Key.tool] = tool_table
    elif doc[Key.tool].get(Key.pdv) is None:  # type: ignore
        doc[Key.tool][Key.pdv] = pdv_table  # type: ignore
    else:
        doc[Key.tool][Key.pdv].update(pdv_table)  # type: ignore

    build_system_table = (
        tomlkit.table().add(Key.requires, _DEFAULT_REQUIRES).add(Key.build_backend, _DEFAULT_BUILD_BACKEND)
    )

    if doc.get(Key.build_system) is None:
        doc[Key.build_system] = build_system_table
    else:
        doc[Key.build_system].update(build_system_table)  # type: ignore

    # Poetry 2.0.0+
    if doc.get(Key.project) is not None:
        if doc[Key.project].get(Key.version) is not None:
            del doc[Key.project][Key.version]

        if doc[Key.project].get(Key.dynamic) is None:
            doc[Key.project][Key.dynamic] = [Key.version]
        else:
            doc[Key.project][Key.dynamic].append(Key.version)

        if doc[Key.tool].get(Key.poetry) is None:
            doc[Key.tool][Key.poetry] = tomlkit.table().add(Key.version, "0.0.0")
        else:
            doc[Key.tool][Key.poetry][Key.version] = "0.0.0"

    return doc


def show() -> None:
    pyproject_path = _get_pyproject_path()
    if pyproject_path is None:
        raise RuntimeError("Unable to find pyproject.toml")

    pyproject = tomlkit.parse(pyproject_path.read_bytes().decode("utf-8"))
    config = _get_config(pyproject)
    version = _get_version(config)

    print(version[0])
