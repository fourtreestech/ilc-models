# ilc-models

![version](https://img.shields.io/badge/version-0.3.0-blue)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Ffourtreestech%2Filc-models%2Fmain%2Fpyproject.toml)
![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

**ilc-models** contains all data models for the *ILC* project.

It's a set of pure Pydantic v2 models with no I/O — a `League` of `Match`
objects, each with its `Lineups`, `Goal`/`Card`/`Substitution` events, and
the `TableRow` results computed from them, plus `User` and `UserPublic`
models for accounts. Its only dependencies are `pydantic` (with the email
extra) and `argon2-cffi`, which `User` uses to hash passwords. This package
is the shared data contract used across the `ilc-api`, `ilc-app` and
`ilc-admin` repositories, so a field change here is a breaking change for
all three.

## Installation

Requires Python 3.12 or later.

```bash
pip install ilc-models
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add ilc-models
```

## Quick start

```python
from ilc_models import League, Match, Teams, Score

league = League(
    league_id=1,
    name="Premiership",
    year=2025,
    start="2025-08-01",
    end="2026-05-01",
    current=True,
    coverage={"lineups": True},
    teams=["Team A", "Team B"],
    rounds={
        "1": [
            Match(
                match_id=1,
                kickoff="2025-08-09T15:00:00+01:00",
                round="1",
                teams=Teams(home="Team A", away="Team B"),
                status="FT",
                score=Score(home=2, away=1),
            )
        ]
    },
)

for row in league.table():
    print(row)
```

## Model map

```
League
 rounds: dict[str, list[Match]]
    Match
       teams: Teams          # home / away team names
       score: Score          # home / away goals
       goals: list[Goal]
       cards: list[Card]
       substitutions: list[Substitution]
       lineups: Lineups
          home: Lineup
          away: Lineup
             starting: list[tuple[int, BasePlayer]]   # shirt_no, player
             subs: list[tuple[int, BasePlayer]]
```

`Goal`, `Card`, `Substitution` and `LineupStatus` all subclass the abstract
`BaseEvent` and are aliased together as `Event`. `League.players` holds
every `Player` who has featured in the league, keyed by `player_id` as a
string.

Users are modelled separately: `User` (the stored shape, including
`password_hash`) subclasses `UserPublic` (`email`, `username` and `status`).

## Users

```python
from ilc_models import User

user = User.create("alice@example.com", "correct horse battery staple")

user.verify_password("correct horse battery staple")  # True
user.verify_password("wrong")  # False

# After a successful login, upgrade the hash if its parameters are outdated
attempt = "correct horse battery staple"
if user.verify_password(attempt) and user.needs_rehash():
    user.set_password(attempt)
    # ...then persist the user
```

`User.create` hashes the password with argon2 and never stores it. `username`
defaults to the part of the email address before the `@`, and `status` to
`"pending"` (the other value is `"active"`); both can be passed as keyword
arguments. To load a user from the database, pass the stored hash instead:
`User(email=..., username=..., password_hash=...)`. Supplying both `password` and
`password_hash` raises an error.

> **Warning:** `User.model_dump()` includes `password_hash`. Anything that
> leaves the API should use `UserPublic` (e.g. FastAPI's
> `response_model=UserPublic`).

## Conventions worth knowing

A few behaviours are deliberate and easy to trip over — see the [full
usage guide](https://ilc-models.readthedocs.io/en/latest/usage.html) for
detail:

- **`Goal.team` is the team credited with the goal, not the scorer's team.**
  For an own goal the scorer belongs to the opposing team — call
  `Match.event_team(event)` to resolve the team a player in an event
  actually plays for.
- **Player equality compares `player_id` alone** (falling back to `name`
  only when both IDs are `0`), because the upstream API spells player names
  differently in event payloads versus player downloads.
- **`League.table()` models the Scottish-style split** — once a team has
  played more than `League.split` matches, the table freezes the top/bottom
  halves by position at the split point and sorts each half independently.
  `League.split` is the number of matches each team plays before the split;
  the default of `0` means no split.
- **The `team`, `teams`, `h2h` and `player` filters on `League.matches()`
  are alternatives, not combinable.** If you pass more than one, only the
  first applies, in that order. `League.match_players()` works the same way
  (without `player`), and `Match.players()` prefers `teams` over `team`.
- **Dates are validated ISO strings, not `date` objects.** `Match.kickoff`
  is a full offset-aware timestamp; `League.start`/`end` and
  `Deduction.date` are `yyyy-mm-dd`. Use `Match.date` to get a
  `datetime.date`.
- **`EventTime.plus` (stoppage time) is only valid at the end of a half** —
  i.e. when `minutes` is 45, 90, 105 or 120.

## Documentation

Full API reference and usage guide:
[ilc-models.readthedocs.io](https://ilc-models.readthedocs.io/)

See [CHANGELOG.md](./CHANGELOG.md) for release history.

## Development

Task runner is [`just`](https://github.com/casey/just); Python tooling is
[`uv`](https://docs.astral.sh/uv/).

```bash
just check   # ruff check --fix, ruff format, then ty check (type checking)
just test    # run tests with pytest
just cov     # pytest with coverage, then regenerate the coverage badge
just docs    # build the Sphinx docs locally
just tox     # run the tests across Python 3.12-3.14 and lowest/highest dependencies
```

## License

MIT — see [LICENSE.txt](./LICENSE.txt).
