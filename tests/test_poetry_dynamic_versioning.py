from pathlib import Path

import poetry_dynamic_versioning as plugin

root = Path(__file__).parents[1]


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


def test__get_config__without_plugin_customizations():
    config = plugin.get_config(root)
    assert config["vcs"] == "any"
    assert config["style"] is None
    assert config["subversion"]["tag-dir"] == "tags"


def test__get_config__with_plugin_customizations():
    config = plugin.get_config(root / "tests" / "project")
    assert config["vcs"] == "git"
    assert config["style"] == "semver"
    assert config["subversion"]["tag-dir"] == "alt/tags"
