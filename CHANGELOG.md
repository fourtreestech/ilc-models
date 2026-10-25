# Changelog

## [Unreleased]

### Added

- Add required `username` and `status` (`"pending"` or `"active"`, default `"pending"`) fields to `UserPublic`, and so to `User`
- Add `username` and `status` parameters to `User.create()`; `username` defaults to the part of the email address before the `@`

## [0.3.0] - 2026-10-19

### Added

- Add `UserPublic` model, the public view of a user (`email`, validated as `EmailStr`)
- Add `User` model, the stored view of a user, extending `UserPublic` with an argon2 `password_hash` (hidden from `repr`)
- Add `User.create()`, `User.verify_password()`, `User.needs_rehash()` and `User.set_password()` methods
- A `User` can be built from either a plain text `password` (hashed on validation) or a stored `password_hash`, but not both

### Changed

- Add `argon2-cffi` and `pydantic[email]` as runtime dependencies

### Documentation

- Document the `User` and `UserPublic` models in the README and usage guide
- Correct the usage guide's description of `League.events()` and document how the `matches()` filters, deductions and `League.split` behave
- Complete missing `Returns:` sections and clarify several field descriptions in the docstrings
- Fix the docs requirements lockfile, which was missing the new dependencies and so broke the Read the Docs build

## [0.2.4] - 2026-08-23

### Added

- Add `Match.event_team()` method
- Add `Match.played_for()` method
- Add `player` parameter to `League.matches()` method

### Fixed

- Fix `TableRow.from_tuple()` losing the `deducted` field, so `as_tuple()`/`from_tuple()` round-trips no longer silently drop points deductions
- Fix date validation to reject impossible calendar dates such as month 19 or 29 February in a non-leap year, as well as malformed ones, on `Player.dob`, `Match.kickoff`, `Deduction.date` and `League.start`/`end`

### Documentation

- Convert docstrings to Google style, correct inaccurate content, add missing documentation, standardise mood/markup
- Expand `README.md` and the Sphinx docs with a model map, worked examples, and the package's non-obvious conventions
- Add a Read the Docs link to the project metadata

## [0.2.3] - 2026-02-05

### Changed

- Add `teams` parameter to `Match.players()` method
- Add `Match.involves_any()` method
- Add `Match.h2h()` method
- Add `teams` and `h2h` parameters to `League.matches()` method
- Add `teams` and `h2h` parameters to `League.match_players()` method

## [0.2.2] - 2026-01-21

### Changed

- Add `team` parameter to `Match.players()` method
- Add `League.match_players()` method

## [0.2.1] - 2025-11-12

### Changed

- Add form to `TableRow.from_tuple` method

## [0.2.0] - 2025-11-10

### Breaking

- Add `form` field to `RowTuple` class

### Changed

- Convert `RowTuple` to `typing.NamedTuple` type

## [0.1.8] - 2025-07-26

### Changed

- Odd number of teams puts the extra team into the top half of the split

## [0.1.7] - 2025-07-14

### Changed

- Add `Match.replace_event()` method

## [0.1.6] - 2025-07-13

### Changed

- Add `Match.delete_event()` method

## [0.1.5] - 2025-06-11

### Changed

- Add `team` parameter to `League.update_player()`

## [0.1.4] - 2025-06-07

### Changed

- `BasePlayer` equality compares `name` attribute if both players have `player_id` == 0

## [0.1.3] - 2025-05-31

### Changed

- `BasePlayer` equality comparison uses only `player_id` attribute

## [0.1.2] - 2025-05-26

### Changed

- Added `LineupStatus` class

## [0.1.1] - 2025-04-03

### Changed

- Restricted compatible Python versions to 3.12 and above

## [0.1.0] - 2025-03-30

_Initial release._

[Unreleased]: https://github.com/fourtreestech/ilc-models/compare/v0.3.0...HEAD

[0.3.0]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.3.0

[0.2.4]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.2.4

[0.2.3]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.2.3

[0.2.2]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.2.2

[0.2.1]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.2.1

[0.2.0]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.2.0

[0.1.8]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.8

[0.1.7]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.7

[0.1.6]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.6

[0.1.5]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.5

[0.1.4]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.4

[0.1.3]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.3

[0.1.2]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.2

[0.1.1]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.1

[0.1.0]: https://github.com/fourtreestech/ilc-models/releases/tag/v0.1.0
