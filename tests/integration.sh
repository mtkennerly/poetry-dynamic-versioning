set -e

root=$(dirname "$(dirname "$(realpath "$0")")")
dummy=$root/tests/project
do_pip="pip"
do_poetry="poetry"
failed="no"

function setup {
    $do_pip uninstall -y poetry-dynamic-versioning
    cd $root
    rm -rf $root/dist/*
    $do_poetry build
    $do_pip install $root/dist/*.whl
}

function teardown {
    git checkout -- $dummy
    $do_pip uninstall -y poetry-dynamic-versioning
}

function should_fail {
    if "$@"; then
        echo Command did not fail: "$@"
        exit 1
    fi
}

function test_plugin_enabled {
    $do_poetry build -v && \
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

function test_cli_mode_and_substitution {
    poetry-dynamic-versioning && \
    # Changes persist after the command is done:
    should_fail grep 'version = "0.0.999"' $dummy/pyproject.toml && \
    should_fail grep '__version__ = "0.0.0"' $dummy/project/__init__.py
}

function test_dependency_versions {
    $do_poetry install -v && \
    $do_poetry run pip list --format freeze | should_fail grep dependency-dynamic==0.0.888 && \
    $do_poetry run pip list --format freeze | grep dependency-static==0.0.777 && \
    $do_poetry run pip list --format freeze | grep dependency-classic==0.0.666
}

function run_test {
    cd $dummy
    git checkout -- $dummy
    rm -rf $dummy/dist/*
    rm -f $dummy/poetry.lock
    rm -f $dummy/*.whl

    # Wokaround because `poetry build` doesn't like relative path dependencies:
    sed -i "s#path = \"../#path = \"$root/tests/#" $dummy/pyproject.toml

    # Workaround for Windows + Git Bash
    sed -i "s#path = \"/c/#path = \"C:/#" $dummy/pyproject.toml

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
    if [ -z "$1" ]; then
        run_tests
    else
        run_test "$1"
    fi
    teardown > /dev/null 2>&1
    echo "Done"

    if [ "$failed" == "yes" ]; then
        exit 1
    fi
}

main $1
