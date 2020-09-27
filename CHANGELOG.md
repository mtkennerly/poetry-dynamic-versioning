## Unreleased

* Changed:
  * Dropped support for `pip wheel .` and bumped the minimum Poetry version to
    1.0.2 in order to enable fixing the following issue.
* Fixed:
  * The main project's dynamic version would be applied to path/Git dependencies.
    Now, the plugin tracks state and configuration for each dependency separately
    in order to correctly report their versions.
  * `poetry run` did not always clean up after itself.
  * `poetry.semver.version` could not be imported because it was moved to
    `poetry.core.semver.version` starting in Poetry 1.1.0a1.

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
