import argparse

from poetry_dynamic_versioning import (
    get_config,
    _apply_version,
    _enable_cli_mode,
    _get_pyproject_path,
    _get_version,
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
    _enable_cli_mode()
    _parse_args()

    config = get_config()

    pyproject_path = _get_pyproject_path()
    if pyproject_path is None:
        raise RuntimeError("Unable to find pyproject.toml")

    version = _get_version(config, pyproject_path)[1]
    _apply_version(version, config, pyproject_path)
