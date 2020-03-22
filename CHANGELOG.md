## Unreleased

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
