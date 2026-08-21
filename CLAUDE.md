# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Task runner is `just` (see `justfile`); Python tooling is `uv`.

```sh
just check      # ruff check --fix, ruff format, then `ty check` (Astral's type checker)
just test       # uv run pytest
just cov        # pytest with coverage + regenerate the README coverage badge via cov-badge
just sync       # ff-only merge dev -> main, push, switch back to dev
just tag        # tag main with v<version> from pyproject.toml and push
```

Single test / narrower runs:

```sh
uv run pytest tests/test_models.py::TestLeagueTable
uv run pytest tests/test_models.py::TestMatch::test_players_from_team
uv run pytest -p no:randomly    # pytest-randomly shuffles order; disable when bisecting a failure
uvx tox                         # full matrix: Python 3.12 and 3.13
```

There is no `[tool.pytest.ini_options]` section — pytest runs on defaults with `tests/` discovered from the repo root.

## Release workflow

Work happens on `dev`; `main` only ever receives fast-forward merges via `just sync`.

The version string lives in **four** places, kept in sync by bumpver (`[tool.bumpver.file_patterns]` in `pyproject.toml`): `pyproject.toml`, the README badge, `src/ilc_models/__init__.py::__version__`, and `docs/source/conf.py::release`. Never hand-edit them — run `uvx bumpver update --patch` (bumpver is not a project dependency; it commits but does not tag or push). Then add a `CHANGELOG.md` entry by hand (including the link reference at the bottom) and run `just tag`.

## Architecture

Everything is one module: `src/ilc_models/__init__.py`. Pure Pydantic v2 models with no I/O and no dependency beyond `pydantic` — this package is the data contract shared across the ILC repos, so a field change here is a breaking change for `ilc-api`, `ilc-app`, and `ilc-admin`.

Containment: `League` → `rounds: dict[str, list[Match]]` → `Match` → `Lineups` → `Lineup` → `list[tuple[shirt_no, BasePlayer]]`. Events (`Goal`, `Card`, `Substitution`, `LineupStatus`) subclass the abstract `BaseEvent`, each carrying a frozen `event_type` literal discriminator and implementing `players()`; the `Event` union type aliases them.

### Conventions that are easy to violate

**`Goal.team` is the team credited with the goal, not the scorer's team.** For an own goal (`goal_type == "O"`) the scorer belongs to the *opposing* team. `Match.event_team(event)` is the single place that resolves the team a given event's players actually play for, flipping it for own goals and passing everything else through unchanged — `Match.players()`, `League.update_player()`, and `League.player_teams()` all call it rather than re-deriving the flip. New code that filters players or events by team should call `Match.event_team()` too, or it will misattribute own goals.

**`BasePlayer.__eq__` compares `player_id` alone**, falling back to `name` only when both IDs are `0`. This is deliberate: the upstream API spells player names differently in event payloads versus player downloads. Consequently `player in some_list` is an ID-based membership test throughout, and `Player` equality inherits this (it ignores `first_name`, `dob`, etc.).

**`TableRow.__gt__` reverses team-name ordering on ties**, so that the `sorted(..., reverse=True)` in `League.table()` yields alphabetical order among equal teams. Do not "fix" the apparent inversion.

**`League.table()` models the Scottish-style split.** Once any team has played more than `League.split` matches, the table freezes the top/bottom halves by position at the split point — computed by recursing into `self.table(split_point=True)` — and sorts each half independently. An odd team count puts the extra team in the top half. Points deductions apply only when `Deduction.date` is empty (season-start) or falls on/before the last match processed, which is why the loop tracks `last_date`.

**Dates are validated ISO strings, not `date` objects.** `Match.kickoff` requires a full offset-aware timestamp (strict `Field(pattern=...)`), `League.start`/`end` require `yyyy-mm-dd`. Four `WrapValidator` helpers layer a real-calendar check (via `datetime.date`/`datetime.datetime`) on top of each field's regex, so month 19 or 29 February in a non-leap year raises `ValueError` rather than validating: `validate_dob` and `validate_deduction_date` additionally accept the empty string, and `validate_dob` normalises `yyyy-m-d` to zero-padded form; `validate_kickoff` and `validate_date` run after the `Field(pattern=...)` on `Match.kickoff` and `League.start`/`end` respectively. Derive `datetime.date` via `Match.date`.

**`EventTime.plus` is only legal at the end of a half** (45/90/105/120), enforced by a `model_validator(mode="after")`.

`League.head_to_head()` predates `League.matches(h2h=...)`; prefer the parameterised `matches()`/`match_players()` filters (`team`, `teams`, `h2h`) for new code.

## Docs and docstrings

Sphinx autodoc renders the whole module (`docs/source/api.rst` → `automodule:: ilc_models`) and publishes to Read the Docs. Public members need reST-style docstrings matching the existing ones (`:param x:` / `:type x:` / `:returns:` / `:rtype:` / `:raises:`), cross-referencing with `:class:` and `:exc:`. `docs/requirements.txt` is a pinned lockfile for the RTD build and must be updated when the docs dependency group changes.

## Tests

`tests/test_models.py` is a single file of `Test<Model>` classes. Fixtures come from the sibling `ilc_provider` package's Faker provider, exposed as the session-scoped `ilc_fake` fixture in `tests/conftest.py` (`ilc_fake.league()`, `.match()`, `.player()`, `.base_player()`, `.lineup()`, `.table_row()`, …) — prefer these over hand-built models.

Two hazards: `pytest-randomly` shuffles test order, and the `fake_league` fixture is session-scoped but holds mutable models, so a test that mutates it can leak into others. Build a fresh `ilc_fake.league()` when mutating.

Coverage sits at 99%; genuinely unreachable defensive branches are marked `# pragma: no cover`.
