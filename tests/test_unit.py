import os
import textwrap
from pathlib import Path

import pytest
import tomlkit
from dunamai import Version

import poetry_dynamic_versioning as plugin
from poetry_dynamic_versioning import cli

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
    assert plugin._find_higher_file("pyproject.toml", start=root / "tests") == root / "pyproject.toml"
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
    assert plugin._get_version(config)[0] == Version.from_git().serialize()


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
    assert plugin._get_version(config)[0] == "v1+foo"


def test__get_version__format_jinja_with_enforced_style(config):
    config["format-jinja"] = "{% if true %}1+jinja{% endif %}"
    config["style"] = "pvp"
    with pytest.raises(ValueError):
        plugin._get_version(config)


def test__get_version__format_jinja_imports_with_module_only(config):
    config["format-jinja"] = "{{ math.pow(2, 2) }}"
    config["format-jinja-imports"] = [{"module": "math", "item": None}]
    assert plugin._get_version(config)[0] == "4.0"


def test__get_version__format_jinja_imports_with_module_and_item(config):
    config["format-jinja"] = "{{ pow(2, 3) }}"
    config["format-jinja-imports"] = [{"module": "math", "item": "pow"}]
    assert plugin._get_version(config)[0] == "8.0"


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


def test__enable_in_doc__empty():
    doc = tomlkit.parse("")
    updated = cli._enable_in_doc(doc)
    assert (
        tomlkit.dumps(updated)
        == textwrap.dedent(
            """
                [tool.poetry-dynamic-versioning]
                enable = true

                [build-system]
                requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]
                build-backend = "poetry_dynamic_versioning.backend"
            """
        ).lstrip()
    )


def test__enable_in_doc__added_pdv():
    doc = tomlkit.parse(
        textwrap.dedent(
            """
                [tool]
                foo = 1
            """
        )
    )
    updated = cli._enable_in_doc(doc)
    assert tomlkit.dumps(updated) == textwrap.dedent(
        """
            [tool]
            foo = 1

            [tool.poetry-dynamic-versioning]
            enable = true

            [build-system]
            requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]
            build-backend = "poetry_dynamic_versioning.backend"
        """
    )


def test__enable_in_doc__updated_enable():
    doc = tomlkit.parse(
        textwrap.dedent(
            """
                [tool.poetry-dynamic-versioning]
                enable = false
            """
        )
    )
    updated = cli._enable_in_doc(doc)
    assert tomlkit.dumps(updated) == textwrap.dedent(
        """
            [tool.poetry-dynamic-versioning]
            enable = true

            [build-system]
            requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]
            build-backend = "poetry_dynamic_versioning.backend"
        """
    )


def test__enable_in_doc__updated_requires():
    doc = tomlkit.parse(
        textwrap.dedent(
            """
                [build-system]
                requires = ["foo"]
            """
        )
    )
    updated = cli._enable_in_doc(doc)
    assert tomlkit.dumps(updated) == textwrap.dedent(
        """
            [build-system]
            requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]
            build-backend = "poetry_dynamic_versioning.backend"

            [tool.poetry-dynamic-versioning]
            enable = true
        """
    )


def test__enable_in_doc__updated_build_backend():
    doc = tomlkit.parse(
        textwrap.dedent(
            """
                [build-system]
                build-backend = ""
            """
        )
    )
    updated = cli._enable_in_doc(doc)
    assert tomlkit.dumps(updated) == textwrap.dedent(
        """
            [build-system]
            build-backend = "poetry_dynamic_versioning.backend"
            requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]

            [tool.poetry-dynamic-versioning]
            enable = true
        """
    )


def test__enable_in_doc__out_of_order_tables():
    doc = tomlkit.parse(
        textwrap.dedent(
            """
                [tool.poetry]
                name = "foo"

                [build-system]
                build-backend = ""

                [tool.poetry.dependencies]
                python = "^3.10"
            """
        )
    )
    updated = cli._enable_in_doc(doc)
    assert tomlkit.dumps(updated) == textwrap.dedent(
        """
            [tool.poetry]
            name = "foo"

            [tool.poetry-dynamic-versioning]
            enable = true
            [build-system]
            build-backend = "poetry_dynamic_versioning.backend"
            requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning>=1.0.0,<2.0.0"]

            [tool.poetry.dependencies]
            python = "^3.10"
        """
    )


def test__substitute_version_in_text__integers_only():
    content = textwrap.dedent(
        """
            __version__: str = "0.0.0"
            __version__ = "0.0.0"
            __version_tuple__ = (0, 0, 0)
        """
    )
    output = textwrap.dedent(
        """
            __version__: str = "0.1.2"
            __version__ = "0.1.2"
            __version_tuple__ = (0, 1, 2)
        """
    )
    version = "0.1.2"
    patterns = plugin._SubPattern.from_config(
        plugin._default_config()["tool"]["poetry-dynamic-versioning"]["substitution"]["patterns"]
    )
    assert plugin._substitute_version_in_text(version, content, patterns) == output


def test__substitute_version_in_text__mixed():
    content = textwrap.dedent(
        """
            __version__: str = "0.0.0"
            __version__ = "0.0.0"
            __version_tuple__ = (0, 0, 0)
        """
    )
    output = textwrap.dedent(
        """
            __version__: str = "0.1.2.dev0-post.4+meta.data"
            __version__ = "0.1.2.dev0-post.4+meta.data"
            __version_tuple__ = (0, 1, 2, "dev0", "post", 4, "meta.data")
        """
    )
    version = "0.1.2.dev0-post.4+meta.data"
    patterns = plugin._SubPattern.from_config(
        plugin._default_config()["tool"]["poetry-dynamic-versioning"]["substitution"]["patterns"]
    )
    assert plugin._substitute_version_in_text(version, content, patterns) == output
