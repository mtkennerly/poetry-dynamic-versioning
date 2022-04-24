import argparse
import sys

from poetry_dynamic_versioning import (
    _get_config_from_path,
    _apply_version,
    _get_pyproject_path,
    _get_version,
    _state,
)


def _parse_args(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the dynamic version to all relevant files and leave the changes in-place."
            " This allows you to activate the plugin behavior on demand and inspect the result."
            " Your configuration will be detected from pyproject.toml as normal."
        )
    )
    parser.parse_args(argv)


def main() -> None:
    try:
        _state.cli_mode = True
        _parse_args()

        config = _get_config_from_path()

        pyproject_path = _get_pyproject_path()
        if pyproject_path is None:
            raise RuntimeError("Unable to find pyproject.toml")

        version = _get_version(config)
        print("Version: {}".format(version), file=sys.stderr)
        name = _apply_version(version, config, pyproject_path, retain=True)
        if _state.projects[name].substitutions:
            print("Files with substitutions:", file=sys.stderr)
            for file_name in _state.projects[name].substitutions:
                print("  - {}".format(file_name), file=sys.stderr)
        else:
            print("Files with substitutions: none", file=sys.stderr)
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
