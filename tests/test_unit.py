import os
from pathlib import Path

import pytest
from dunamai import Version

import poetry_dynamic_versioning as plugin

root = Path(__file__).parents[1]


@pytest.fixture
def config():
    return plugin._default_config()["tool"]["poetry-dynamic-versioning"]


def test__deep_merge_dicts():
    assert plugin._deep_merge_dicts({}, {}) == {}
    assert plugin._deep_merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}
    assert plugin._deep_merge_dicts({"a": {"b": 2}}, {"a": 1}) == {"a": 1}
    assert plugin._deep_merge_dicts({"a": {"b": 2}}, {"a": {"c": 3}}) == {"a": {"b": 2, "c": 3}}


def test__find_higher_file():
    assert plugin._find_higher_file("pyproject.toml", start=root) == root / "pyproject.toml"
    assert (
        plugin._find_higher_file("pyproject.toml", start=root / "tests") == root / "pyproject.toml"
    )
    assert (
        plugin._find_higher_file("pyproject.toml", start=root / "tests" / "project")
        == root / "tests" / "project" / "pyproject.toml"
    )


def test__get_config_from_path__without_plugin_customizations():
    config = plugin._get_config_from_path(root)
    assert config["vcs"] == "any"
    assert config["style"] is None
    assert config["tag-dir"] == "tags"


def test__get_config_from_path__with_plugin_customizations():
    config = plugin._get_config_from_path(root / "tests" / "project")
    assert config["vcs"] == "git"
    assert config["style"] == "semver"
    assert config["tag-dir"] == "alt/tags"


def test__get_version__defaults(config):
    assert plugin._get_version(config) == Version.from_git().serialize()


def test__get_version__invalid_vcs(config):
    config["vcs"] = "invalid"
    with pytest.raises(ValueError):
        plugin._get_version(config)


def test__get_version__invalid_style(config):
    config["style"] = "invalid"
    with pytest.raises(ValueError):
        plugin._get_version(config)


def test__get_version__format_jinja(config):
    os.environ["FOO"] = "foo"
    config["format-jinja"] = "{% if true %}v1+{{ env['FOO'] }}{% endif %}"
    assert plugin._get_version(config) == "v1+foo"


def test__get_version__format_jinja_with_enforced_style(config):
    config["format-jinja"] = "{% if true %}1+jinja{% endif %}"
    config["style"] = "pvp"
    with pytest.raises(ValueError):
        plugin._get_version(config)


def test__get_version__format_jinja_imports_with_module_only(config):
    config["format-jinja"] = "{{ math.pow(2, 2) }}"
    config["format-jinja-imports"] = [{"module": "math"}]
    assert plugin._get_version(config) == "4.0"


def test__get_version__format_jinja_imports_with_module_and_item(config):
    config["format-jinja"] = "{{ pow(2, 3) }}"
    config["format-jinja-imports"] = [{"module": "math", "item": "pow"}]
    assert plugin._get_version(config) == "8.0"


def test__get_override_version__bypass():
    env = {plugin._BYPASS_ENV: "0.1.0"}
    assert plugin._get_override_version(None, env) == "0.1.0"
    assert plugin._get_override_version("foo", env) == "0.1.0"


def test__get_override_version__override():
    env = {plugin._OVERRIDE_ENV: "foo=0.1.0,bar=0.2.0"}
    assert plugin._get_override_version(None, env) is None
    assert plugin._get_override_version("foo", env) == "0.1.0"
    assert plugin._get_override_version("bar", env) == "0.2.0"
    assert plugin._get_override_version("baz", env) is None


def test__get_override_version__combined():
    env = {plugin._BYPASS_ENV: "0.0.0", plugin._OVERRIDE_ENV: "foo = 0.1.0, bar = 0.2.0"}
    assert plugin._get_override_version(None, env) == "0.0.0"
    assert plugin._get_override_version("foo", env) == "0.1.0"
