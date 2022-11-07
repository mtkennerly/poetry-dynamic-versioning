import argparse
import sys

from poetry_dynamic_versioning import (
    _get_and_apply_version,
    _state,
    _validate_config,
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

        errors = _validate_config()
        if errors:
            print("Configuration issues:", file=sys.stderr)
            for error in errors:
                print("  - {}".format(error), file=sys.stderr)

        name = _get_and_apply_version(retain=True, force=True)
        if not name:
            raise RuntimeError("Unable to determine a dynamic version")

        print("Version: {}".format(_state.projects[name].version), file=sys.stderr)
        if _state.projects[name].substitutions:
            print("Files with substitutions:", file=sys.stderr)
            for file_name in _state.projects[name].substitutions:
                print("  - {}".format(file_name), file=sys.stderr)
        else:
            print("Files with substitutions: none", file=sys.stderr)
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
