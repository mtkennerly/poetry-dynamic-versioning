# Dynamic versioning plugin for Poetry

This package is a plugin for [Poetry](https://github.com/sdispater/poetry)
to enable dynamic versioning based on tags in your version control system,
powered by [Dunamai](https://github.com/mtkennerly/dunamai).

Since Poetry does not yet officially support plugins
(refer to [this issue](https://github.com/sdispater/poetry/issues/693))
as of the time of writing on 2019-06-04, this package takes some novel
liberties to make the functionality possible. As soon as official support
lands, this plugin will be updated to do things the official way.

## Installation

Python 3.5 or newer is required.

* Run `pip install poetry-dynamic-versioning`
* Add this to your pyproject.toml:
  ```toml
  [tool.poetry-dynamic-versioning]
  enable = true
  ```

Note that you must install the plugin in your global Python installation,
**not** as a dependency in pyroject.toml, because the virtual environment
that Poetry creates cannot see Poetry itself and therefore cannot patch it.

## Configuration

In your pyproject.toml file, you may configure the following options:

* `[tool.poetry-dynamic-versioning]`: General options.
  * `enable`: Boolean. Default: false. Since the plugin has to be installed
    globally, this setting is an opt-in per project. This setting will likely
    be removed once plugins are officially supported.
  * `vcs`: String. This is the version control system to check for a version.
    One of: `any` (default), `git`, `mercurial`, `darcs`, `bazaar`, `subversion`.
  * `metadata`: Boolean. Default: unset. If true, include the commit hash in
    the version, and also include a dirty flag if `dirty` is true. If unset,
    metadata will only be included if you are on a commit without a version tag.
  * `dirty`: Boolean. Default: false. If true, include a dirty flag in the
    metadata, indicating whether there are any uncommitted changes.
  * `pattern`: String. This is a regular expression which will be used to find
    a tag representing a version. There must be a named capture group `base`
    with the main part of the version, and optionally you can also have groups
    named `pre_type` and `pre_number` for prereleases. The default is
    `v(?P<base>\d+\.\d+\.\d+)((?P<pre_type>[a-zA-Z]+)(?P<pre_number>\d+))?`.
  * `format`: String. Default: unset. This defines a custom output format for
    the version. Available substitutions:
      * `{base}`
      * `{epoch}`
      * `{pre_type}`
      * `{pre_number}`
      * `{post}`
      * `{dev}`
      * `{commit}`
      * `{dirty}`
  * `style`: String. Default: unset. One of: `pep440`, `semver`, `pvp`.
    These are preconfigured output formats. If you set both a `style` and
    `format`, then the format will be validated against the style's rules.
    If `style` is unset, then formats won't be validated, and the version
    will conform to PEP 440.
  * `latest-tag`: Boolean. Default: false. If true, then only check the latest
    tag for a version, rather than looking through all the tags until a suitable
    one is found to match the `pattern`.
* `[tool.poetry-dynamic-versioning.subversion]`: Options specific to Subversion.
  * `tag-dir`: String. Default: `tags`. This is the location of tags relative
    to the root.

Simple example:

```toml
[tool.poetry-dynamic-versioning]
enable = true
vcs = "git"
style = "semver"
```

## Implementation

In order to side-load plugin functionality into Poetry, this package
does the following:

* Upon installation, it delivers a `zzz_poetry_dynamic_versioning.pth`
  file to your Python site-packages directory. This forces Python to
  automatically load the plugin after all other modules have been loaded
  (or at least those alphabetically prior to `zzz`).
* It patches `builtins.__import__` so that, whenever the first import from
  Poetry finishes, `poetry.console.main` will be patched. The reason we have
  to wait for a Poetry import is in case you've used the get-poetry.py script,
  in which case there is a gap between when Python is fully loaded and when
  `~/.poetry/bin/poetry` adds the Poetry lib folder to the PYTHONPATH.
* The patched version of `poetry.console.main` will then, when called,
  additionally patch `poetry.poetry.Poetry.create` to replace the version
  from your pyproject.toml file with the dynamically generated version.

## Development

This project is managed using [Poetry](https://poetry.eustace.io).
Development requires Python 3.6+ because of [Black](https://github.com/ambv/black).

* If you want to take advantage of the default VSCode integration, then first
  configure Poetry to make its virtual environment in the repository:
  ```
  poetry config settings.virtualenvs.in-project true
  ```
* After cloning the repository, activate the tooling:
  ```
  poetry install
  poetry run pre-commit install
  ```
* Run unit tests:
  ```
  poetry run pytest --cov
  poetry run tox
  ```
* Run integration tests:
  ```
  ./tests/integration.sh
  ```
  [Git Bash](https://gitforwindows.org) is recommended for Windows.
