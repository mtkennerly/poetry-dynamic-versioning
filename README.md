# Dynamic versioning plugin for Poetry
This is a Python 3.7+ plugin for [Poetry 1.2.0+](https://github.com/sdispater/poetry)
and [Poetry Core 1.0.0+](https://github.com/python-poetry/poetry-core)
to enable dynamic versioning based on tags in your version control system,
powered by [Dunamai](https://github.com/mtkennerly/dunamai). Many different
version control systems are supported, including Git and Mercurial; please
refer to the Dunamai page for the full list (and minimum supported version
where applicable).

`poetry-dynamic-versioning` provides a build backend that patches Poetry Core
to enable the versioning system in PEP 517 build frontends.
When installed with the `plugin` feature (i.e., `poetry-dynamic-versioning[plugin]`),
it also integrates with the Poetry CLI to trigger the versioning in commands like `poetry build`.

For Poetry 1.1.x, you can use an older version of `poetry-dynamic-versioning` (0.17.1 or earlier)
that relied on a `*.pth` import hack, but this is no longer supported,
so you should migrate to the standardized plugin and Poetry 1.2.0+.

## Installation
If you've previously installed the deprecated `poetry-dynamic-versioning-plugin` package,
be sure to uninstall it before proceeding.

* Run: `poetry self add "poetry-dynamic-versioning[plugin]"`
* Add this section to your pyproject.toml:
  ```toml
  [tool.poetry-dynamic-versioning]
  enable = true
  ```
* Include the plugin in the `build-system` section of pyproject.toml
  for interoperability with PEP 517 build frontends:

  ```toml
  [build-system]
  requires = ["poetry-core>=1.0.0", "poetry-dynamic-versioning"]
  build-backend = "poetry_dynamic_versioning.backend"
  ```

  This is a thin wrapper around `poetry.core.masonry.api`.

Poetry's typical `version` setting is still required in `[tool.poetry]`,
but you are encouraged to use `version = "0.0.0"` as a standard placeholder.

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
  * `enable` (boolean, default: false): Since the plugin has to be installed
    globally, this setting is an opt-in per project. This setting will likely
    be removed once plugins are officially supported.
  * `vcs` (string, default: `any`): This is the version control system to check for a version.
    One of: `any`, `git`, `mercurial`, `darcs`, `bazaar`, `subversion`, `fossil`, `pijul`.
  * `metadata` (boolean, default: unset): If true, include the commit hash in
    the version, and also include a dirty flag if `dirty` is true. If unset,
    metadata will only be included if you are on a commit without a version tag.
    This is ignored when `format` or `format-jinja` is used.
  * `tagged-metadata` (boolean, default: false): If true, include any tagged
    metadata discovered as the first part of the metadata segment.
    Has no effect when `metadata` is set to false.
    This is ignored when `format` or `format-jinja` is used.
  * `dirty` (boolean, default: false): If true, include a dirty flag in the
    metadata, indicating whether there are any uncommitted changes.
    Has no effect when `metadata` is set to false.
    This is ignored when `format` or `format-jinja` is used.
  * `pattern` (string): This is a regular expression which will be used to find
    a tag representing a version. When this is unset, Dunamai's default pattern is used.

    There must be a capture group named `base`
    with the main part of the version. Optionally, it may contain another two
    groups named `stage` and `revision` for prereleases, and it may contain a
    group named `tagged_metadata` to be used with the `tagged-metadata` option.
    There may also be a group named `epoch` for the PEP 440 concept.

    If the `base` group is not included, then this will be interpreted as a
    named preset from the Dunamai `Pattern` class. This includes:
    `default`, `default-unprefixed` (makes the `v` prefix optional).

    You can check the default for your installed version of Dunamai by running this command:
    ```
    poetry run python -c "import dunamai; print(dunamai.Pattern.Default.regex())"
    ```

    Remember that backslashes must be escaped (`\\`) in the TOML file.
  * `format` (string, default: unset): This defines a custom output format for
    the version. Available substitutions:

    * `{base}`
    * `{stage}`
    * `{revision}`
    * `{distance}`
    * `{commit}`
    * `{dirty}`
    * `{tagged_metadata}`
    * `{branch}`
    * `{branch_escaped}` which omits any non-letter/number characters
    * `{timestamp}` of the current commit, which expands to YYYYmmddHHMMSS as UTC

    Example: `v{base}+{distance}.{commit}`
  * `format-jinja` (string, default: unset): This defines a custom output format
    for the version, using a [Jinja](https://pypi.org/project/Jinja2) template.
    When this is set, `format` is ignored.

    Available variables:

    * `base` (string)
    * `stage` (string or None)
    * `revision` (integer or None)
    * `distance` (integer)
    * `commit` (string)
    * `dirty` (boolean)
    * `tagged_metadata` (string or None)
    * `version` (dunumai.Version)
    * `env` (dictionary of environment variables)
    * `branch` (string or None)
    * `branch_escaped` (string or None)
    * `timestamp` (string or None)

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
  * `format-jinja-imports` (array of tables, default: empty): This defines
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
  * `style` (string, default: unset): One of: `pep440`, `semver`, `pvp`.
    These are preconfigured output formats. If you set both a `style` and
    a `format`, then the format will be validated against the style's rules.
    If `style` is unset, the default output format will follow PEP 440,
    but a custom `format` will only be validated if `style` is set explicitly.
  * `latest-tag` (boolean, default: false): If true, then only check the latest
    tag for a version, rather than looking through all the tags until a suitable
    one is found to match the `pattern`.
  * `bump` (boolean, default: false): If true, then increment the last part of
    the version `base` by 1, unless the `stage` is set, in which case increment
    the `revision` by 1 or set it to a default of 2 if there was no `revision`.
    Does nothing when on a commit with a version tag.

    Example, if there have been 3 commits since the `v1.3.1` tag:
    * PEP 440 with `bump = false`: `1.3.1.post3.dev0+28c1684`
    * PEP 440 with `bump = true`: `1.3.2.dev3+28c1684`
  * `tag-dir` (string, default: `tags`): This is the location of tags relative
    to the root. This is only used for Subversion.
  * `tag-branch` (string, default: unset): Branch on which to find tags, if different than the
    current branch. This is only used for Git currently.
  * `full-commit` (boolean, default: false): If true, get the full commit hash
    instead of the short form. This is only used for Git and Mercurial.
  * `strict` (boolean, default: false):
    If true, then fail instead of falling back to 0.0.0 when there are no tags.
* `[tool.poetry-dynamic-versioning.substitution]`: Insert the dynamic version
  into additional files other than just pyproject.toml. These changes will be
  reverted when the plugin deactivates.
  * `files` (array of strings): Globs for any files that need substitutions. Default:
    `["*.py", "*/__init__.py", "*/__version__.py", "*/_version.py"]`.
    To disable substitution, set this to an empty list.
  * `patterns` (array of strings): Regular expressions for the text to replace.
    Each regular expression must have two capture groups, which are any
    text to preserve before and after the replaced text. Default:
    `["(^__version__\s*(?::.*?)?=\s*['\"])[^'\"]*(['\"])"]`.

    Remember that the backslashes must be escaped (`\\`) in the TOML file.
  * `folders` (array of tables, default: empty): List of additional folders to
    check for substitutions.

    Each table supports these options:

    * `path` (string, required): Path to the folder.
    * `files` (array of strings, optional): Override `substitution.files` for this folder.
    * `patterns` (array of strings, optional): Override `substitution.patterns` for this folder.

    If you use an `src` layout, you may want to keep the default `files`/`patterns`
    and just specify the following:

    ```toml
    folders = [
      { path = "src" }
    ]
    ```

    This will check the default file globs (e.g., `./*.py`)
    as well as the same file globs inside of `src` (e.g., `./src/*.py`).

Simple example:

```toml
[tool.poetry-dynamic-versioning]
enable = true
vcs = "git"
style = "semver"
```

## Environment variables
In addition to the project-specific configuration above,
you can apply some global overrides via environment variables.

* `POETRY_DYNAMIC_VERSIONING_BYPASS`:
  Use this to bypass the VCS mechanisms and use a static version instead.
  This is mainly for distro package maintainers who need to patch existing releases,
  without needing access to the original repository.
* `POETRY_DYNAMIC_VERSIONING_COMMANDS`:
  You can set a comma-separated list of Poetry commands during which to activate the versioning.
  For example, `build,publish` will limit the dynamic versioning to those two commands.

## Command line mode
The plugin also has a command line mode for execution on demand.
This mode applies the dynamic version to all relevant files and leaves
the changes in-place, allowing you to inspect the result.
Your configuration will be detected from pyproject.toml as normal,
but the `enable` option is not necessary.

To activate this mode, either use `poetry dynamic-versioning` (provided by the `plugin` feature)
or `poetry-dynamic-versioning` (standalone script with default features).

## VCS archives
Sometimes, you may only have access to an archive of a repository (e.g., a zip file) without the full history.
The plugin can still detect a version in some of these cases.
Refer to [the Dunamai documentation](https://github.com/mtkennerly/dunamai#vcs-archives) for more info.

## Caveats
* When using Git, remember that lightweight tags do not store their creation time.
  Therefore, if a commit has multiple lightweight tags,
  we cannot reliably determine which one should be considered the newest.
  The solution is to use annotated tags instead.
* The dynamic version is not available during `poetry run` or `poetry shell`.
* Regarding PEP 517 support:

  `pip wheel .` and `pip install .` will work with new enough Pip versions
  that default to in-tree builds or support the `--use-feature=in-tree-build`
  option. Older versions of Pip will not work because they create an isolated
  copy of the source code that does not contain the version control history.

  If you want to build wheels of your dependencies, you can do the following,
  although local path-based dependencies may not work:

  ```
  poetry export -f requirements.txt -o requirements.txt --without-hashes
  pip wheel -r requirements.txt
  ```
