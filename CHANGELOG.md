## v1.4.1 (2024-09-10)

* Fixed:
  * The `enable` command would fail when the pyproject.toml tables were out of order.

## v1.4.0 (2024-06-17)

* Added:
  * The plugin now supports Poetry's upcoming PEP-621 functionality.
    More info here: https://github.com/python-poetry/poetry/issues/3332

    If your pyproject.toml defines `tool.poetry.name`,
    then the plugin will preserve its existing behavior.

    However, if your pyproject.toml:

    * does not define `tool.poetry.name`
    * defines `project.name`
    * defines `project.dynamic` to include `"version"`
    * does not define `project.version`

    ...then the plugin will enable its PEP-621 functionality.

    Because PEP-621 support is not yet released and finalized in Poetry itself,
    it is also subject to change in the plugin.

    ([Prototyped by edgarrmondragon](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/181))

## v1.3.0 (2024-04-29)

* Added:
  * `pattern-prefix` option to add a prefix to the version tag pattern.
  * `ignore-untracked` option to control the detection of dirty state.
  * `from-file` config section to read a version from a file instead of the VCS.
  * `POETRY_DYNAMIC_VERSIONING_DEBUG` environment variable for some logging.
* Changed:
  * Updated Dunamai to 1.21.0+ for the latest features.

## v1.2.0 (2023-12-02)

* Added:
  * `initial-content-jinja` option in `tool.poetry-dynamic-versioning.files` section.
* Fixed:
  * Line ending style was not preserved in some cases because of the default behavior of `pathlib.Path.read_text`.
    To avoid this, `pathlib.Path.read_bytes` is used instead now.
    ([Contributed by nardi](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/157))

## v1.1.1 (2023-10-27)

* Fixed:
  * Custom substitutions in pyproject.toml weren't cleaned up correctly.
    This was because the plugin would record the "original" content of the file
    after the `version` and `enable` fields had already been changed.
    Now, substitutions are reverted first before reverting `version` and `enable`.

## v1.1.0 (2023-10-01)

* Added:
  * `tool.poetry-dynamic-versioning.files` config section.
    This allows you to create a file in a default state before applying substitutions to it.
    You can also leave the substitutions in place when the plugin deactivates.

## v1.0.1 (2023-08-21)

* Fixed:
  * Compatibility with poetry-core 1.7.0, which removed the `poetry.core.semver` module.
  * The `enable` command now constrains the plugin version to `>=1.0.0,<2.0.0`
    to protect against any potential API changes.

## v1.0.0 (2023-08-18)

* Fixed:
  * Running `poetry dynamic-versioning` followed by `poetry build`
    would leave the plugin enabled in the sdist's pyproject.toml.

## v0.25.0 (2023-07-11)

* Added:
  * `fix-shallow-repository` option to attempt to automatically fix shallow repositories.
    Currently, this only supports Git and will run `git fetch --unshallow`.
* Changed:
  * Updated Dunamai to 1.18.0+ for the latest features.

## v0.24.0 (2023-06-30)

* Added:
  * `POETRY_DYNAMIC_VERSIONING_COMMANDS_NO_IO`
    environment variable to prevent the plugin from modifying files during certain commands.
    The plugin still sets the dynamic version in memory so that Poetry itself can write it as needed.
* Changed:
  * During `poetry version`, the plugin still activates, but no longer modifies pyproject.toml.

## v0.23.0 (2023-06-13)

* Added:
  * CLI `enable` subcommand to enable the plugin in pyproject.toml.
  * Support for `POETRY_DYNAMIC_VERSIONING_OVERRIDE` environment variable.
  * `mode` option for substitution to support `__version_tuple__` style.
* Changed:
  * CLI: `poetry dynamic-versioning` now outputs a summary of the changes,
    the same way that `poetry-dynamic-versioning` already did.

## v0.22.0 (2023-05-19)

* Added:
  * The plugin will print a warning for shallow Git repositories
    (and any other `Concern`s reported by Dunamai in the future).
    This becomes an error with `strict = true`.
* Changed:
  * Updated Dunamai to 1.17.0+ for the latest features and bug fixes.

## v0.21.5 (2023-05-15)

* Fixed:
  * Compatibility with poetry-core 1.6.0+.
* Changed:
  * `CHANGELOG.md` and `tests` are now included in sdists.

## v0.21.4 (2023-02-21)

* Fixed:
  * In the Poetry CLI mode and standalone script mode,
    `path` dependencies received the same dynamic version as the active project.
    This issue did not affect the build backend mode.
* Changed:
  * Updated Dunamai to 1.16.0+ for the latest features and bug fixes.

## v0.21.3 (2022-12-23)

* Fixed:
  * Resolved a deprecation warning when used with Poetry Core 1.3.0+.
    ([Contributed by edgarrmondragon](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/106))

## v0.21.2 (2022-12-16)

* Fixed:
  * Line endings were not necessarily preserved because of the default behavior of `pathlib.Path.write_text`.
    To avoid this, `pathlib.Path.write_bytes` is used instead now.

## v0.21.1 (2022-11-08)

* Fixed:
  * Warning for invalid config was printed to stdout instead of stderr.

## v0.21.0 (2022-11-07)

* Added:
  * The plugin now prints a warning if its configuration is invalid.
    Right now, this just checks for unknown keys.
  * A `strict` option to prevent falling back to `0.0.0` when there are no tags.
* Changed:
  * Updated Dunamai to 1.14.0+ for the latest features.
    This adds support for VCS archival files, namely ones produced by `git archive` and `hg archive`.
    Refer to [the Dunamai documentation](https://github.com/mtkennerly/dunamai#vcs-archives) for more info.

## v0.20.0 (2022-10-18)

* Changed:
  * Updated Dunamai to 1.13.2+ for the latest features and bug fixes.
    In particular, this fixes an error when parsing Git output with `showSignature = true` configured.

## v0.19.0 (2022-09-16)

* Fixed:
  * When using `poetry build`, the plugin did not properly disable itself in the
    copy of pyproject.toml included in source distributions, causing failures
    when trying to install them.
* Added:
  * Support for activating the dynamic versioning only for certain Poetry commands
    (environment variable: `POETRY_DYNAMIC_VERSIONING_COMMANDS`).

## poetry-dynamic-versioning: v0.18.0 (2022-09-05)

* Changed:
  * The minimum supported Python version is now 3.7.
  * The minimum supported Poetry version is now 1.2.0.
  * Import hacks have been eliminated in favor of a PEP 517 build backend wrapper
    around Poetry Core.
  * The two flavors of poetry-dynamic-versioning are now combined into one package
    via the optional `plugin` feature.

## poetry-dynamic-versioning-plugin: v0.4.0 (2022-09-05)

* Deprecated the name `poetry-dynamic-versioning-plugin`
  in favor of a newly unified `poetry-dynamic-versioning`.

## poetry-dynamic-versioning-plugin: v0.3.2 (2022-05-25)

* Fixed:
  * `poetry` did not work correctly when in a folder without a pyproject.toml.
  * `poetry plugin show` did not work correctly.

## poetry-dynamic-versioning: v0.17.1 & poetry-dynamic-versioning-plugin: v0.3.1 (2022-05-19)

* Fixed:
  * CLI mode failed when pyproject.toml did not specify `enable = true`.

## poetry-dynamic-versioning: v0.17.0 & poetry-dynamic-versioning-plugin: v0.3.0 (2022-05-13)

* Added:
  * Option `tool.poetry-dynamic-versioning.substitution.folders`.

## poetry-dynamic-versioning: v0.16.0 & poetry-dynamic-versioning-plugin: v0.2.0 (2022-05-07)

* Changed:
  * Option `tool.poetry-dynamic-versioning.subversion.tag-dir` is now `tool.poetry-dynamic-versioning.tag-dir`.
* Added:
  * Option `tool.poetry-dynamic-versioning.tag-branch`.
  * Option `tool.poetry-dynamic-versioning.full-commit`.

## poetry-dynamic-versioning-plugin: v0.1.0 (2022-04-28)

* Changed:
  * The Poetry 1.2+ plugin now has a new name, `poetry-dynamic-versioning-plugin`,
    and this is its first release as a separate package.

    The import-hack-based pseudo-plugin will continue to be called `poetry-dynamic-versioning`.

## poetry-dynamic-versioning: v0.15.0 (2022-04-28)

* Changed:
  * Internal improvements/refactoring to unify code base with `poetry-dynamic-versioning-plugin`,
    which is released as a separate package. These changes should not affect
    users of `poetry-dynamic-versioning`.

## v1.0.0b3 (2022-04-24)

* Fixed:
  * The plugin can now update versions for dependencies that also use the plugin.

## v1.0.0b2 (2022-04-15)

* Fixed:
  * The plugin maintained its own copy of the default `pattern`, which meant that
    it could fall behind the copy in Dunamai and lead to surprising behavior.
    The plugin now automatically uses the latest default from Dunamai directly
    when you do not customize it in the plugin settings.

## v0.14.1 (2022-04-14)

* Fixed:
  * The plugin maintained its own copy of the default `pattern`, which meant that
    it could fall behind the copy in Dunamai and lead to surprising behavior.
    The plugin now automatically uses the latest default from Dunamai directly
    when you do not customize it in the plugin settings.

## v1.0.0b1 (2022-03-10)

* Changed:
  * Implemented the official Poetry plugin interface.

## v0.14.0 (2022-03-09)

* Changed:
  * The build backend is now poetry-core.
    ([Contributed by fabaff](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/63))
  * The default list of `substitution.patterns` now handles `__version__`
    when it has a type annotation.
    ([Draft by da2ce7](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/64))
* Added:
  * Option to bypass the version control system and set a hard-coded version
    in an environment variable called `POETRY_DYNAMIC_VERSIONING_BYPASS`.
    ([Draft by jonringer](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/69))
  * `branch`, `branch_escaped`, and `timestamp` formatting variables.

## v0.13.1 (2021-08-09)

* Fixed an oversight where the default version tag pattern would only find
  tags with exactly three parts in the base (e.g., `v1.0.0` and `v1.2.3`).
  This is now relaxed so that `v1`, `v1.2.3.4`, and so on are also recognized.

## v0.13.0 (2021-05-26)

* Changed:
  * Broadened version range of Jinja2 dependency to support projects that need
    a newer version.
  * Bumped the minimum Poetry version to 1.1.0, since the above Jinja2 change
    seemed to trip up Poetry 1.0.10 (on Python 3.7 and 3.8, but not 3.5 or 3.6,
    for some reason).
* Fixed:
  * The plugin did not work on Fedora inside of Pip's isolated build
    environment, because the plugin would be loaded before some of its
    dependencies. Now, those imports are delayed until needed.

## v0.12.7 (2021-05-20)

* Fixed:
  * Parsing files containing special UTF-8 characters would result in an error.
    Files are now assumed to be UTF-8.
    ([Contributed by rhorenov](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/50))

## v0.12.6 (2021-04-19)

* Fixed:
  * The previous `bump` fix only applied to `format-jinja`. It has now been
    fixed for other scenarios as well.

## v0.12.5 (2021-04-18)

* Fixed:
  * When the `bump` option was enabled, the version would be bumped even when on
    a commit with a version tag. Now, no bumping occurs when on such a commit.

## v0.12.4 (2021-03-05)

* Fixed:
  * An incompatibility with `tox-poetry-installer` where the working directory
    was received as a `str` instead of a `Path`.
    ([Contributed by cburgess](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/41))

## v0.12.3 (2021-02-19)

* Fixed:
  * Previously, when building a source distribution with `poetry build`, the
    plugin's config section would retain the `enable = true` setting, which
    would then cause an error when installing the artifact since the VCS info
    would not be available.
    (This was not an issue for wheels generated by `poetry build`.)

    The dynamic version from build time is still present in the source
    distribution, so there is no need for the plugin at install time.
    Therefore, the plugin now temporarily sets `enable = false` so that that
    value will be placed in the source distribution, then restores the original
    setting for development purposes.

## v0.12.2 (2021-01-30)

* Fixed:
  * Another possible exception when applying patches if only `poetry-core` was
    installed and not the Poetry tool, particularly combined with Tox.

## v0.12.1 (2021-01-04)

* Fixed:
  * Possible exception when applying patches if only `poetry-core` was
    installed and not the Poetry tool.

## v0.12.0 (2020-12-05)

* Added:
  * `tagged-metadata` option, for the corresponding Dunamai feature.
    ([Contributed by mariusvniekerk](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/32))

## v0.11.0 (2020-11-21)

* Added:
  * `bump` option.
* Fixed:
  * `poetry shell` did not clean up after itself.

## v0.10.0 (2020-10-08)

* Added:
  * Support for patching `poetry-core` when used as a standalone build system.

## v0.9.0 (2020-09-27)

* Changed:
  * Dropped support for `pip wheel .` and bumped the minimum Poetry version to
    1.0.2 in order to enable fixing the following issue.
* Fixed:
  * The main project's dynamic version would be applied to path/Git dependencies.
    Now, the plugin tracks state and configuration for each dependency separately
    in order to correctly report their versions.
  * `poetry run` did not always clean up after itself.
  * `poetry.semver.version` could not be imported because it was moved to
    `poetry.core.semver.version` starting in Poetry 1.1.0a1. The plugin can now
    handle either location.

## v0.8.3 (2020-08-07)

* Fixed a possible issue with string interning in glob handling.
  ([Contributed by mariusvniekerk](https://github.com/mtkennerly/poetry-dynamic-versioning/pull/18))

## v0.8.2 (2020-07-06)

* Fixed an issue with Python 3.5 compatibility.
  (Contributed by [gsemet](https://github.com/gsemet))
* Increased minimum Dunamai version to propagate the latest updates.

## v0.8.1 (2020-05-29)

* Fixed an issue where CLI mode did not persist the change to pyproject.toml.
  This problem was missed because of an issue in the integration tests,
  which are fixed now as well.

## v0.8.0 (2020-05-28)

* Added the option `format-jinja-imports`.
* Added support for Pip's PEP 517 isolated builds.
* In CLI mode:
  * Improved handling of error conditions.
  * Added output of the generated version and any modified files.
* Removed handling for Poetry versions prior to 1.0.0.
* Avoid writing files if the content does not need to be changed.

## v0.7.0 (2020-05-14)

* Added a CLI mode.

## v0.6.0 (2020-03-22)

* Expose new Dunamai functions via `format-jinja`:
  * `bump_version`
  * `serialize_pep440`
  * `serialize_pvp`
  * `serialize_semver`

## v0.5.0 (2020-02-12)

* Added the `format-jinja` option.

## v0.4.0 (2019-12-13)

* Added the ability to update the version in other files than pyproject.toml.

## v0.3.2 (2019-12-13)

* Fixed an issue with Poetry 1.0.0b2 and newer where the original version
  would not be restored after `poetry run`.
  (Contributed by [lmoretto](https://github.com/lmoretto))

## v0.3.1 (2019-11-28)

* Fixed [#3](https://github.com/mtkennerly/poetry-dynamic-versioning/issues/3)
  where the plugin would revert not only the dynamic version change in pyproject.toml,
  but also any other changes, such as the addition of new dependencies.
  (Contributed by [lmoretto](https://github.com/lmoretto))

## v0.3.0 (2019-10-27)

* Updated for Dunamai v1.0.0:
  * Added support for Fossil.
  * Better error reporting, such as when no tags match the expected pattern.
  * Custom formatting:
    * Renamed `{post}` to `{distance}`
    * Renamed `{pre_type}` to `{stage}`
    * Renamed `{pre_number}` to `{revision}`
    * Removed `{epoch}`
    * Removed `{dev}`

## v0.2.0 (2019-10-19)

* Added support for Poetry 1.0.0b2.

## v0.1.0 (2019-06-05)

* Initial release.
