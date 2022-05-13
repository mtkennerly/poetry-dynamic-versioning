#!/usr/bin/env bash
set -e

root=$(dirname "$(dirname "$(realpath "$0")")")
dummy=$root/tests/project
do_pip="pip"
do_poetry_pip="pip"
do_poetry="poetry"
failed="no"
mode="${1:-patch}"
installation="${2:-pip}"
specific_test="$3"

if [ "$mode" == "plugin" ]; then
    do_pdv="$do_poetry dynamic-versioning"
elif [ "$installation" == "poetry-pip" ]; then
    poetry_bin="${XDG_DATA_HOME:-~/.local/share}/pypoetry/venv/bin"
    eval poetry_bin="$poetry_bin"
    do_poetry_pip="${poetry_bin}/pip"
    do_pdv="${poetry_bin}/poetry-dynamic-versioning"
else
    do_pdv="poetry-dynamic-versioning"
fi

function setup {
    $do_pip uninstall -y poetry-dynamic-versioning poetry-dynamic-versioning-plugin
    if [ "$do_poetry_pip" != "$do_pip" ]; then
        $do_poetry_pip uninstall -y poetry-dynamic-versioning poetry-dynamic-versioning-plugin
    fi

    cd $root
    rm -rf $root/dist/*
    $do_poetry build

    case $installation in
        pip)
            $do_pip install $root/dist/*.whl
            ;;
        poetry-pip)
            $do_poetry_pip install $root/dist/*.whl
            ;;
        poetry-plugin)
            $do_poetry plugin add $root/dist/*.whl
            ;;
    esac
}

function teardown {
    git checkout -- $dummy $root/tests/dependency-*
    case $installation in
        pip)
            $do_pip uninstall -y poetry-dynamic-versioning poetry-dynamic-versioning-plugin
            ;;
        poetry-pip)
            $do_poetry_pip uninstall -y poetry-dynamic-versioning poetry-dynamic-versioning-plugin
            ;;
        poetry-plugin)
            $do_poetry plugin remove poetry-dynamic-versioning-plugin
            ;;
    esac
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

function test_cli_mode_and_substitution {
    $do_pdv \
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

function test_poetry_core_as_build_system {
    sed -i 's/requires = .*/requires = ["poetry-core"]/' $dummy/pyproject.toml && \
    sed -i 's/build-backend = .*/build-backend = "poetry.core.masonry.api"/' $dummy/pyproject.toml && \
    $do_poetry build -v && \
    ls $dummy/dist | grep .whl && \
    ls $dummy/dist | should_fail grep 0.0.999
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
