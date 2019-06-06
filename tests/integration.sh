set -e

root=$(dirname "$(dirname "$(realpath "$0")")")
dummy=$root/tests/project

function setup {
    pip uninstall -y poetry-dynamic-versioning
    cd $root
    rm -rf $root/dist/*
    poetry build
    pip install $root/dist/*.whl
}

function teardown {
    git checkout -- $dummy
    pip uninstall -y poetry-dynamic-versioning
}

function test_plugin_enabled {
    poetry build -v
    ls $dummy/dist | grep -v 0.0.999
}

function test_plugin_disabled {
    sed -i 's/enable = .*/enable = false/' pyproject.toml
    poetry build -v
    ls $dummy/dist | grep 0.0.999
}

function test_invalid_config_for_vcs {
    sed -i 's/vcs = .*/vcs = "invalid"/' pyproject.toml
    if poetry build -v; then
        return -1
    else
        return 0
    fi
}

function run_test {
    cd $dummy
    git checkout -- $dummy
    rm -rf $dummy/dist/*

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
