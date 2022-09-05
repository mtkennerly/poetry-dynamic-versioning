#!/usr/bin/env bash
set -e

root=$(dirname "$(dirname "$(realpath "$0")")")
dummy=$root/tests/project
do_pix="pipx"
do_poetry="poetry"
failed="no"
specific_test="$1"

function setup {
    $do_poetry self remove poetry-dynamic-versioning || true

    cd $root
    rm -rf $root/dist/*
    $do_poetry build
    rm -rf $dummy/.venv

    uname_id="$(uname -s)"
    case "${uname_id}" in
        MINGW*)
            whl_pattern="$(pwd -W)/dist/*.whl"
            ;;
        *)
            whl_pattern="$root/dist/*.whl"
            ;;
    esac
    whl_files=( $whl_pattern )
    echo WHL FILE: "${whl_files[0]}", from pattern: "${whl_pattern}"
    $do_poetry self add ${whl_files[0]}[plugin]
}

function teardown {
    git checkout -- $dummy $root/tests/dependency-*
    $do_poetry self remove poetry-dynamic-versioning || true
}

function should_fail {
    if "$@"; then
        echo Command did not fail: "$@"
        exit 1
    fi
}

function test_plugin_enabled {
    $do_poetry build -v && \
    ls $dummy/dist | grep .whl && \
    ls $dummy/dist | should_fail grep 0.0.999
}

function test_plugin_disabled {
    sed -i 's/enable = .*/enable = false/' $dummy/pyproject.toml && \
    $do_poetry build -v && \
    ls $dummy/dist | grep 0.0.999
}

function test_plugin_disabled_without_plugin_section {
    sed -i 's/tool.poetry-dynamic-versioning/tool.poetry-dynamic-versioning-x/' $dummy/pyproject.toml && \
    $do_poetry build -v && \
    ls $dummy/dist | grep 0.0.999
}

function test_plugin_disabled_without_pyproject_file {
    cd ~ && \
    $do_poetry --help
}

function test_invalid_config_for_vcs {
    sed -i 's/vcs = .*/vcs = "invalid"/' $dummy/pyproject.toml && \
    should_fail $do_poetry build -v
}

function test_keep_pyproject_modifications {
    package="cachy"
    # Using --optional to avoid actually installing the package
    $do_poetry add --optional $package && \
    # Make sure pyproject.toml contains the new package dependency
    grep $package $dummy/pyproject.toml
}

function test_poetry_run {
    # The original version is restored before the command runs:
    $do_poetry run grep 'version = "0.0.999"' $dummy/pyproject.toml && \
    # Make sure original version number is still in place:
    grep 'version = "0.0.999"' $dummy/pyproject.toml
}

function test_poetry_shell {
    if [ -z "$CI" ]; then
        # Make sure original version number is still in place afterwards:
        ($SHELL -c "cd $dummy && $do_poetry shell" &) && \
        sleep 3 && \
        grep 'version = "0.0.999"' $dummy/pyproject.toml
    fi
}

function test_plugin_cli_mode_and_substitution {
    $do_poetry dynamic-versioning \
    # Changes persist after the command is done:
    should_fail grep 'version = "0.0.999"' $dummy/pyproject.toml && \
    should_fail grep '__version__: str = "0.0.0"' $dummy/project/__init__.py && \
    should_fail grep '__version__ = "0.0.0"' $dummy/project/__init__.py \
    should_fail grep '<0.0.0>' $dummy/project/__init__.py
}

function extra_standalone_cli_mode_and_substitution {
    poetry-dynamic-versioning \
    # Changes persist after the command is done:
    should_fail grep 'version = "0.0.999"' $dummy/pyproject.toml && \
    should_fail grep '__version__: str = "0.0.0"' $dummy/project/__init__.py && \
    should_fail grep '__version__ = "0.0.0"' $dummy/project/__init__.py \
    should_fail grep '<0.0.0>' $dummy/project/__init__.py
}

function test_cli_mode_and_substitution_without_enable {
    sed -i 's/enable = .*/enable = false/' $dummy/pyproject.toml && \
    $do_poetry dynamic-versioning \
    # Changes persist after the command is done:
    should_fail grep 'version = "0.0.999"' $dummy/pyproject.toml && \
    should_fail grep '__version__: str = "0.0.0"' $dummy/project/__init__.py && \
    should_fail grep '__version__ = "0.0.0"' $dummy/project/__init__.py \
    should_fail grep '<0.0.0>' $dummy/project/__init__.py
}

function test_dependency_versions {
    $do_poetry install -v && \
    $do_poetry run pip list --format freeze | grep dependency-dynamic== && \
    $do_poetry run pip list --format freeze | should_fail grep dependency-dynamic==0.0.888 && \
    $do_poetry run pip list --format freeze | grep dependency-static==0.0.777 && \
    $do_poetry run pip list --format freeze | grep dependency-classic==0.0.666
}

function extra_poetry_core_as_build_system {
    cd $root/tests/dependency-dynamic
    sed -i 's/requires = .*/requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning"]/' pyproject.toml && \
    sed -i 's/build-backend = .*/build-backend = "poetry_dynamic_versioning.backend"/' pyproject.toml && \
    pip wheel . --no-build-isolation --wheel-dir dist
    ls dist | grep .whl && \
    ls dist | should_fail grep 0.0.888
}

function test_bumping_enabled {
    sed -i 's/vcs = .*/bump = true/' $dummy/pyproject.toml && \
    sed -i 's/style = .*/style = "pep440"/' $dummy/pyproject.toml && \
    $do_poetry build -v && \
    ls $dummy/dist | should_fail grep 0.0.999 && \
    ls $dummy/dist | should_fail grep .post
}

function test_bypass {
    POETRY_DYNAMIC_VERSIONING_BYPASS=1.2.3 $do_poetry build -v && \
    ls $dummy/dist | grep 1.2.3
}

function test_plugin_show {
    $do_poetry self show
}

function run_test {
    cd $dummy
    git checkout -- $dummy
    rm -rf $dummy/dist/*
    rm -f $dummy/poetry.lock
    rm -f $dummy/*.whl

    name="$1"
    output=$(eval "$name 2>&1") && result=$? || result=$?
    if [[ $result -eq 0 ]]; then
        echo "  $name -- PASSED"
    else
        echo "  $name -- FAILED"
        echo "$output" | fold -w 76 | awk '{ print "    " $0 }'
        failed="yes"
    fi
}

function run_tests {
    for func in $(declare -F | cut -c 12- | grep test_); do
        run_test $func
    done
}

function main {
    echo "Starting..."
    setup > /dev/null 2>&1
    if [ -z "$specific_test" ]; then
        run_tests
    else
        run_test "$specific_test"
    fi
    teardown > /dev/null 2>&1
    echo "Done"

    if [ "$failed" == "yes" ]; then
        exit 1
    fi
}

main $1
