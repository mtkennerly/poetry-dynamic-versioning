# Dynamic versioning plugin for Poetry
[![Version](https://img.shields.io/pypi/v/poetry-dynamic-versioning)](https://pypi.org/project/poetry-dynamic-versioning)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This package is a plugin for [Poetry](https://github.com/sdispater/poetry)
to enable dynamic versioning based on tags in your version control system,
powered by [Dunamai](https://github.com/mtkennerly/dunamai). Many different
version control systems are supported, including Git and Mercurial; please
refer to the Dunamai page for the full list (and minimum supported version
where applicable).

Since Poetry does not yet officially support plugins
(refer to [this issue](https://github.com/sdispater/poetry/issues/693))
as of the time of writing on 2019-10-19, this package takes some novel
liberties to make the functionality possible. As soon as official support
lands, this plugin will be updated to do things the official way.

## Installation
Python 3.5 or newer and Poetry 1.0.2 or newer are required.

* Run `pip install poetry-dynamic-versioning`
* Add this section to your pyproject.toml:
  ```toml
  [tool.poetry-dynamic-versioning]
  enable = true
  ```
* Include the plugin in the `build-system` section of pyproject.toml
  for interoperability:
  ```toml
  [build-system]
  requires = ["poetry>=1.0.2", "poetry-dynamic-versioning"]
  build-backend = "poetry.masonry.api"
  ```

Note that you must install the plugin in your global Python installation,
**not** as a dev-dependency in pyproject.toml, because the virtual environment
that Poetry creates cannot see Poetry itself and therefore cannot patch it.

With the minimal configuration above, the plugin will automatically take effect
when you run commands such as `poetry build`. It will update the version in
pyproject.toml, then revert the change when the plugin deactivates. If you want
to include a `__version__` variable in your code, just put a placeholder in the
appropriate file and configure the plugin to update it (see below) if it isn't
one of the defaults. You are encouraged to use `__version__ = "0.0.0"` as a
standard placeholder.

## Configuration
In your pyproject.toml file, you may configure the following options:

* `[tool.poetry-dynamic-versioning]`: General options.
  * `enable`: Boolean. Default: false. Since the plugin has to be installed
    globally, this setting is an opt-in per project. This setting will likely
    be removed once plugins are officially supported.
  * `vcs`: String. This is the version control system to check for a version.
    One of: `any` (default), `git`, `mercurial`, `darcs`, `bazaar`,
    `subversion`, `fossil`.
  * `metadata`: Boolean. Default: unset. If true, include the commit hash in
    the version, and also include a dirty flag if `dirty` is true. If unset,
    metadata will only be included if you are on a commit without a version tag.
  * `dirty`: Boolean. Default: false. If true, include a dirty flag in the
    metadata, indicating whether there are any uncommitted changes.
  * `pattern`: String. This is a regular expression which will be used to find
    a tag representing a version. There must be a named capture group `base`
    with the main part of the version, and optionally you can also have groups
    named `stage` and `revision` for prereleases. The default is
    `^v(?P<base>\d+\.\d+\.\d+)(-?((?P<stage>[a-zA-Z]+)\.?(?P<revision>\d+)?))?$`.
  * `format`: String. Default: unset. This defines a custom output format for
    the version. Available substitutions:

    * `{base}`
    * `{stage}`
    * `{revision}`
    * `{distance}`
    * `{commit}`
    * `{dirty}`

    Example: `v{base}+{distance}.{commit}`
  * `format-jinja`: String. Default: unset. This defines a custom output format
    for the version, using a [Jinja](https://pypi.org/project/Jinja2) template.
    When this is set, `format` is ignored.

    Available variables:

    * `base` (string)
    * `stage` (string or None)
    * `revision` (integer or None)
    * `distance` (integer)
    * `commit` (string)
    * `dirty` (boolean)
    * `env` (dictionary of environment variables)

    Available functions:

    * `bump_version` ([from Dunamai](https://github.com/mtkennerly/dunamai/blob/dc2777cdcc5eeff61c10602e33b1a0dc0bb0357b/dunamai/__init__.py#L786-L797))
    * `serialize_pep440` ([from Dunamai](https://github.com/mtkennerly/dunamai/blob/dc2777cdcc5eeff61c10602e33b1a0dc0bb0357b/dunamai/__init__.py#L687-L710))
    * `serialize_semver` ([from Dunamai](https://github.com/mtkennerly/dunamai/blob/dc2777cdcc5eeff61c10602e33b1a0dc0bb0357b/dunamai/__init__.py#L740-L752))
    * `serialize_pvp` ([from Dunamai](https://github.com/mtkennerly/dunamai/blob/dc2777cdcc5eeff61c10602e33b1a0dc0bb0357b/dunamai/__init__.py#L766-L775))

    Simple example:

    ```toml
    format-jinja = "{% if distance == 0 %}{{ base }}{% else %}{{ base }}+{{ distance }}.{{ commit }}{% endif %}"
    ```

    Complex example:

    ```toml
    format-jinja = """
        {%- if distance == 0 -%}
            {{ serialize_pep440(base, stage, revision) }}
        {%- elif revision is not none -%}
            {{ serialize_pep440(base, stage, revision + 1, dev=distance, metadata=[commit]) }}
        {%- else -%}
            {{ serialize_pep440(bump_version(base), stage, revision, dev=distance, metadata=[commit]) }}
        {%- endif -%}
    """
    ```
  * `format-jinja-imports`: Array of tables. Default: empty. This defines
    additional things to import and make available to the `format-jinja`
    template. Each table must contain a `module` key and may also contain an
    `item` key. Consider this example:

    ```toml
    format-jinja-imports = [
        { module = "foo" },
        { module = "bar", item = "baz" },
    ]
    ```

    This is roughly equivalent to:

    ```python
    import foo
    from bar import baz
    ```

    `foo` and `baz` would then become available in the Jinja formatting.
  * `style`: String. Default: unset. One of: `pep440`, `semver`, `pvp`.
    These are preconfigured output formats. If you set both a `style` and
    a `format`, then the format will be validated against the style's rules.
    If `style` is unset, the default output format will follow PEP 440,
    but a custom `format` will only be validated if `style` is set explicitly.
  * `latest-tag`: Boolean. Default: false. If true, then only check the latest
    tag for a version, rather than looking through all the tags until a suitable
    one is found to match the `pattern`.
* `[tool.poetry-dynamic-versioning.subversion]`: Options specific to Subversion.
  * `tag-dir`: String. Default: `tags`. This is the location of tags relative
    to the root.
* `[tool.poetry-dynamic-versioning.substitution]`: Insert the dynamic version
  into additional files other than just pyproject.toml. These changes will be
  reverted when the plugin deactivates.
  * `files`: List of globs for any files that need substitutions. Default:
    `["*.py", "*/__init__.py", "*/__version__.py", "*/_version.py"]`.
    To disable substitution, set this to an empty list.
  * `patterns`: List of regular expressions for the text to replace.
    Each regular expression must have two capture groups, which are any
    text to preserve before and after the replaced text. Default:
    `["(^__version__\s*=\s*['\"])[^'\"]*(['\"])"]`.

Simple example:

```toml
[tool.poetry-dynamic-versioning]
enable = true
vcs = "git"
style = "semver"
```

## Command line mode
The plugin also has a command line mode for execution on demand.
This mode applies the dynamic version to all relevant files and leaves
the changes in-place, allowing you to inspect the result.
Your configuration will be detected from pyproject.toml as normal,
but the `enable` option is not necessary.

To activate this mode, run the `poetry-dynamic-versioning` command
in your console.

## Caveats
* The dynamic version is not available during `poetry run` because Poetry
  uses [`os.execvp()`](https://docs.python.org/2/library/os.html#os.execvp).
* Regarding PEP 517 support:

  `pip wheel .` will not work, because Pip creates an isolated copy of the
  source code, which does not contain the Git history and therefore cannot
  determine the dynamic version.

  If you want to build wheels of your dependencies, you **can** do the following,
  but it won't work with path dependencies for the same reason as above:

  ```
  poetry export -f requirements.txt -o requirements.txt --without-hashes
  pip wheel -r requirements.txt
  ```

## Implementation
In order to side-load plugin functionality into Poetry, this package
does the following:

* Upon installation, it delivers a `zzz_poetry_dynamic_versioning.pth`
  file to your Python site-packages directory. This forces Python to
  automatically load the plugin after all other modules have been loaded
  (or at least those alphabetically prior to `zzz`).
* It first tries to patch `poetry.factory.Factory.create_poetry` and
  `poetry.console.commands.run.RunCommand` directly. If they cannot be
  imported, then it patches `builtins.__import__` so that, whenever those
  classes are first imported, then they will be patched. The reason we may have
  to wait for these to be imported is in case you've used the get-poetry.py
  script, in which case there is a gap between when Python is fully loaded and
  when `~/.poetry/bin/poetry` adds the Poetry lib folder to the PYTHONPATH.
* The patched version of `Factory` will compute and apply the dynamic version.
* The patched version of `RunCommand` will deactivate the plugin before
  executing the passed command, because otherwise we will not be able to do
  any cleanup afterwards.

## Development
Please refer to [CONTRIBUTING.md](CONTRIBUTING.md).
