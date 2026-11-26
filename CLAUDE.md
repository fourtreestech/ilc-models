# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Task runner is `just` (see `justfile`); Python tooling is `uv`.

```sh
just check      # ruff check --fix, ruff format, then `ty check` (Astral's type checker)
just test       # uv run pytest
just cov        # pytest with coverage + regenerate the README coverage badge via cov-badge
just upgrade    # uv lock --upgrade, uv sync, regenerate docs/requirements.txt, then run tox
just tox        # uvx tox
just docs       # sphinx-build -W --keep-going into docs/build/html
just bump       # uvx bumpver update --patch (commits; doesn't tag or push)
just sync       # ff-only merge dev -> main, push, switch back to dev
just tag        # tag main with v<version> from pyproject.toml and push
just publish    # rm -rf dist, uv build, then uv publish to PyPI
```

Single test / narrower runs:

```sh
uv run pytest tests/test_league.py::TestLeagueTable
uv run pytest tests/test_match.py::TestMatch::test_players_from_team
uv run pytest -p no:randomly    # pytest-randomly shuffles order; disable when bisecting a failure
uvx tox                         # full matrix: Python 3.12, 3.13, 3.14, 3.15 (pinned to `uv.lock`), plus `lowest` (3.12 with `--resolution lowest-direct`: lowest versions of direct dependencies only, transitive ones resolve to newest) and `highest` (3.15 with the newest releases, ignoring `uv.lock`)
```

There is no `[tool.pytest.ini_options]` section — pytest runs on defaults with `tests/` discovered from the repo root.

tox and tox-uv versions come only from `[tool.tox] requires` in `pyproject.toml`: `uvx tox` provisions them into `.tox/.tox`. Don't add them to a dependency group, or the `uvx tox` and `uv run tox` routes can drift apart.

## Release workflow

Work happens on `dev`; `main` only ever receives fast-forward merges via `just sync`.

The version string lives in **four** places, kept in sync by bumpver (`[tool.bumpver.file_patterns]` in `pyproject.toml`): `pyproject.toml`, the README badge, `src/ilc_models/__init__.py::__version__`, and `docs/source/conf.py::release`. Never hand-edit them — run `just bump`, which wraps `uvx bumpver update --patch` (bumpver is not a project dependency; it commits but does not tag or push). Then add a `CHANGELOG.md` entry by hand (including the link reference at the bottom), run `just tag`, and finally `just publish` to build and upload to PyPI. `just publish` authenticates via a PyPI API token (`pypi-…`) read from `.pypi.token` at the repo root — gitignored, so a fresh clone needs it recreated by hand.

## Architecture

The package is split into submodules by domain under `src/ilc_models/`:

| Module | Contents |
|---|---|
| `player.py` | `BasePlayer`, `Player`, `validate_dob` |
| `lineup.py` | `Lineup`, `Lineups` |
| `event.py` | `EventTime`, `BaseEvent`, `Goal`, `Card`, `Substitution`, `LineupStatus`, the `Event` union |
| `match.py` | `Teams`, `Score`, `Match`, `EventInfo`, `validate_kickoff` |
| `table.py` | `RowTuple`, `TableRow`, `Deduction`, `validate_deduction_date` |
| `league.py` | `League`, `validate_date` |
| `user.py` | `UserPublic`, `User`, `validate_created_at`, `validate_teams`, and the private `_ph` / `_hash_password` |

Imports between submodules only flow one way (`player` → `lineup`/`event` → `match` → `table` → `league`; `user` is standalone), so keep them that way to avoid cycles. Pydantic resolves field annotations at runtime, so cross-module model imports must be real imports, not `TYPE_CHECKING`-only.

`__init__.py` holds `__version__` and re-exports every public name, with an explicit `__all__`. Every consumer imports from the top level (`from ilc_models import League`), never from a submodule, so the submodule layout is internal. **A new public name must be imported into `__init__.py` and added to `__all__`**; `tests/test_init.py` fails if a public class or function defined in a submodule is missing from `__all__`.

These are Pydantic v2 models with no I/O — this package is the data contract shared across the ILC repos, so a field change here is a breaking change for `ilc-api`, `ilc-app`, and `ilc-admin`. Its only dependencies are `pydantic[email]` (for `EmailStr`) and `argon2-cffi`, which `User` uses for password hashing through the private module-level `_ph` hasher in `user.py`; don't add any others.

`User` is the stored shape (Mongo), including `password_hash`, so `model_dump()` includes it. `UserPublic` is the API response shape with no secrets, and `User` subclasses it. Fields that must never leave the API go on `User` only; `ilc-api` should declare `response_model=UserPublic`. Request bodies in `ilc-api` use their own schemas and never `UserPublic`/`User`, so server-set fields such as `created_at` can't come from clients; keep it that way.

`User.verify_password()` never modifies the user. To upgrade outdated hashes, the caller does `if user.verify_password(attempt) and user.needs_rehash(): user.set_password(attempt)` and then persists the user.

Containment: `League` → `rounds: dict[str, list[Match]]` → `Match` → `Lineups` → `Lineup` → `list[tuple[shirt_no, BasePlayer]]`. Events (`Goal`, `Card`, `Substitution`, `LineupStatus`) subclass the abstract `BaseEvent`, each carrying a frozen `event_type` literal discriminator and implementing `players()`; the `Event` union type aliases them.

### Conventions that are easy to violate

**`Goal.team` is the team credited with the goal, not the scorer's team.** For an own goal (`goal_type == "O"`) the scorer belongs to the *opposing* team. `Match.event_team(event)` is the single place that resolves the team a given event's players actually play for, flipping it for own goals and passing everything else through unchanged — `Match.players()`, `League.update_player()`, and `League.player_teams()` all call it rather than re-deriving the flip. New code that filters players or events by team should call `Match.event_team()` too, or it will misattribute own goals.

**`BasePlayer.__eq__` compares `player_id` alone**, falling back to `name` only when both IDs are `0`. This is deliberate: the upstream API spells player names differently in event payloads versus player downloads. Consequently `player in some_list` is an ID-based membership test throughout, and `Player` equality inherits this (it ignores `first_name`, `dob`, etc.).

**`TableRow.__gt__` reverses team-name ordering on ties**, so that the `sorted(..., reverse=True)` in `League.table()` yields alphabetical order among equal teams. Do not "fix" the apparent inversion.

**`League.table()` models the Scottish-style split.** Once any team has played more than `League.split` matches, the table freezes the top/bottom halves by position at the split point — computed by recursing into `self.table(split_point=True)` — and sorts each half independently. An odd team count puts the extra team in the top half. Points deductions apply only when `Deduction.date` is empty (season-start) or falls on/before the last match processed, which is why the loop tracks `last_date`.

**Dates are validated ISO strings, not `date` objects.** `Match.kickoff` requires a full offset-aware timestamp (strict `Field(pattern=...)`), `League.start`/`end` require `yyyy-mm-dd`. Four `WrapValidator` helpers layer a real-calendar check (via `datetime.date`/`datetime.datetime`) on top of each field's regex, so month 19 or 29 February in a non-leap year raises `ValueError` rather than validating: `validate_dob` and `validate_deduction_date` additionally accept the empty string, and `validate_dob` normalises `yyyy-m-d` to zero-padded form; `validate_kickoff` and `validate_date` run after the `Field(pattern=...)` on `Match.kickoff` and `League.start`/`end` respectively. Derive `datetime.date` via `Match.date`. **Exception:** `UserPublic.created_at` is a server-kept timestamp, not football data, so it is an offset-aware UTC `datetime` (stored by ilc-api as a BSON date, which keeps it sortable and queryable). `validate_created_at` treats naive values (pymongo's default) as UTC and converts aware ones to UTC; it defaults to `None` so stored users predating the field stay unknown rather than getting a load-time value, and only `User.create()` sets it.

**`EventTime.plus` is only legal at the end of a half** (45/90/105/120), enforced by a `model_validator(mode="after")`.

`League.head_to_head()` predates `League.matches(h2h=...)`; prefer the parameterised `matches()`/`match_players()` filters (`team`, `teams`, `h2h`) for new code.

## Docs and docstrings

Sphinx autodoc renders the package docstring and then one section per submodule (`docs/source/api.rst` → `automodule:: ilc_models.<submodule>` with `:members:`) and publishes to Read the Docs. A new submodule needs its own section in `api.rst`. The top-level `automodule:: ilc_models` deliberately omits `:members:`, since the re-exports would otherwise document every object twice and fail the `-W` build with duplicate-object warnings. Public members need Google-style docstrings matching the existing ones (`Args:` / `Attributes:` / `Returns:` / `Raises:`, parsed by `sphinx.ext.napoleon`). `ruff`'s `D`/`D401` rules (Google convention, see `[tool.ruff.lint.pydocstyle]`) enforce presence and imperative mood as part of `just check`; `tests/*` and `docs/*` are exempted via `per-file-ignores`.

Style conventions:
- Method/function summaries are imperative ("Return the …", "Get the …", "Sort the …"); class summaries stay descriptive ("Represents a goal.").
- Cross-reference with single backticks only (`` `ClassName` ``, `` `ValueError` ``) — `default_role = "literal"` in `conf.py` renders them as code, so `:class:`/`:exc:`/`:attr:` roles and double backticks are unnecessary and should not be used.
- Pydantic model fields are documented as `Attributes:` on the class docstring rather than `Args:`, with `(default=…)` noted where a field has one. **Exception:** don't add an `Attributes:` section to a `NamedTuple` (e.g. `RowTuple`) — its fields are separate real attributes that autodoc already documents individually, and a Napoleon `Attributes:` block for the same names produces a "duplicate object description" warning that fails `-W` builds. Describe `NamedTuple` fields in prose instead.
- Types are omitted from `Args:`/`Attributes:`/`Returns:` entries — `autodoc_typehints = "description"` and `napoleon_attr_annotations` pull them from the annotations instead, so only the description goes in the docstring. This also means **a method's return type only renders if its docstring has a `Returns:` section** (`autodoc_typehints_description_target = "documented_params"`), so every method with a non-`None` return needs one, including dunders like `__eq__`/`__gt__`/`__len__`/`__bool__`/`__str__`.

Run `just docs` to build the docs locally (`-W`, so any Napoleon/autodoc warning fails the build). `docs/requirements.txt` is a pinned lockfile for the RTD build and must be updated when the docs dependency group changes; `just upgrade` regenerates it with `uv export`.

## Tests

Tests mirror the package layout: one `tests/test_<submodule>.py` per submodule, each holding `Test<Model>` classes (e.g. `test_league.py` has `TestLeague` and `TestLeagueTable`). `tests/test_init.py` checks the public interface: every `__all__` name is exported and is the same object as in its submodule. Fixtures come from the sibling `ilc_provider` package's Faker provider, exposed as the session-scoped `ilc_fake` fixture in `tests/conftest.py` (`ilc_fake.league()`, `.match()`, `.player()`, `.base_player()`, `.lineup()`, `.table_row()`, …) — prefer these over hand-built models.

Two hazards: `pytest-randomly` shuffles test order, and the `fake_league` fixture is session-scoped but holds mutable models, so a test that mutates it can leak into others. Build a fresh `ilc_fake.league()` when mutating.

Coverage sits at 100%; genuinely unreachable defensive branches are marked `# pragma: no cover`.
