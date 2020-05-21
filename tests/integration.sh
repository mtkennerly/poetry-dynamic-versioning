set -e

root=$(dirname "$(dirname "$(realpath "$0")")")
dummy=$root/tests/project
do_pip="pip"
do_poetry="poetry"

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

function test_plugin_enabled {
    $do_poetry build -v
    ! ls $dummy/dist | grep 0.0.999
}

function test_plugin_disabled {
    sed -i 's/enable = .*/enable = false/' $dummy/pyproject.toml
    $do_poetry build -v
    ls $dummy/dist | grep 0.0.999
}

function test_invalid_config_for_vcs {
    sed -i 's/vcs = .*/vcs = "invalid"/' $dummy/pyproject.toml
    if $do_poetry build -v; then
        return -1
    else
        return 0
    fi
}

function test_keep_pyproject_modifications {
    package="cachy"
    # Using --optional to avoid actually installing the package
    $do_poetry add --optional $package
    # Make sure pyproject.toml contains the new package dependency
    grep $package $dummy/pyproject.toml
}

function test_poetry_run {
    # The original version is restored before the command runs:
    $do_poetry run grep 'version = "0.0.999"' $dummy/pyproject.toml
    # Make sure original version number is still in place:
    grep 'version = "0.0.999"' $dummy/pyproject.toml
}

function test_substitution {
    ! $do_poetry run grep '__version__ = "0.0.0"' $dummy/project/__init__.py
    grep '__version__ = "0.0.0"' $dummy/project/__init__.py
}

function test_cli_mode {
    $do_poetry run poetry-dynamic-versioning
    # Changes persist after Poetry is done:
    ! grep 'version = "0.0.999"' $dummy/pyproject.toml
    ! $do_poetry run grep '__version__ = "0.0.0"' $dummy/project/__init__.py
}

function run_test {
    cd $dummy
    git checkout -- $dummy
    rm -rf $dummy/dist/*
    rm -f $dummy/poetry.lock

    name="$1"
    output=$(eval "$name 2>&1") && result=$? || result=$?
    if [[ $result -eq 0 ]]; then
        echo "  $name -- PASSED"
    else
        echo "  $name -- FAILED"
        echo "$output" | fold -w 76 | awk '{ print "    " $0 }'
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
    run_tests
    teardown > /dev/null 2>&1
    echo "Done"
}

main
