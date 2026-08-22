Usage
=====

`ilc-models` is a set of pure Pydantic v2 models with no I/O. There is nothing to
configure and nothing that talks to a network or a database - you build model
instances (typically from JSON returned by an upstream API, or from
`model_validate`), pass them around, and call the methods described below.

Model map
---------

A `League` contains its `rounds`, each round a list of `Match` objects::

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

`Goal`, `Card`, `Substitution` and `LineupStatus` all subclass the abstract
`BaseEvent` and are collectively aliased as `Event`. `League.players` holds
every `Player` who has featured in the league, keyed by `player_id` as a string.

Players
-------

`BasePlayer` is the minimal player reference (`player_id` and `name`) used
everywhere a player is referred to - lineups, event payloads, method
arguments. `Player` extends it with `first_name`, `last_name`, `dob` and
`nationality`; its `base_player` property strips those back down to a
`BasePlayer`.

`BasePlayer.__eq__` compares `player_id` alone, falling back to comparing
`name` only when both players have `player_id == 0`. This is deliberate: the
upstream API spells player names differently in event payloads versus player
downloads, so matching on name would cause spurious mismatches. As a
consequence, `player in some_list` is an ID-based membership test
throughout this package, and `Player` equality inherits it - two `Player`
instances with the same `player_id` are equal even if their `dob` or
`nationality` differ.

Lineups
-------

Each lineup entry is a `(shirt_no, BasePlayer)` tuple, with `shirt_no` as
`0` if it wasn't supplied. `Lineup.starting` is capped at 11 entries by a
`Field` constraint; `Lineup.subs` is unbounded.

`Lineup.sort` and `Lineups.sort` order each part of the lineup by shirt
number, except that the *first* entry in `starting` is assumed to be the
goalkeeper and is always left in place rather than sorted with the rest.
`__bool__` and `__len__` on both classes count players across `starting` and
`subs` combined.

Events
------

`BaseEvent` carries `team` and `time` (an `EventTime`), and declares the
abstract `players()` method that every subclass implements:

* `Goal` - `goal_type` is one of 'N' (normal), 'O' (own goal) or 'P'
  (penalty); `players()` returns the `scorer`.
* `Card` - `color` is 'Y' or 'R'; `players()` returns the carded `player`.
* `Substitution` - `players()` returns `[player_off, player_on]`, the
  player leaving the field followed by the player entering it.
* `LineupStatus` - records whether a player started or came on as a sub
  (`status` is 'starting' or 'sub'); `players()` returns that `player`.
  `League.events` synthesises these on the fly from lineup data rather than
  storing them on `Match`.

Each subclass carries a frozen `event_type` literal ('goal', 'card',
'sub', 'status') as a discriminator, and the four are aliased
together as `Event`.

`EventTime` holds `minutes` (1-120) and `plus`, the stoppage-time minutes
added after a half. A `model_validator` enforces that `plus` is only
non-zero when `minutes` is 45, 90, 105 or 120 - additional time is only
meaningful at the end of a half. `EventTime` supports `==` and `>`
(`functools.total_ordering` fills in the rest), so events sort correctly
by kickoff-relative time; `Match.events()` uses this to merge goals, cards
and substitutions into one chronological list.

Matches
-------

`Match` fields cover identity (`match_id`, `kickoff`, `round`), the
participants (`teams`, a `Teams` of home/away names), and outcome (`status`,
`score`, `goals`, `cards`, `substitutions`, `lineups`).

Two properties derive from `status`/`kickoff`:

* `played` - `True` if `status` is one of 'FT', 'AET' or 'PEN'.
* `date` - the `datetime.date` portion of `kickoff`.

Three predicates filter by team:

* `involves(team)` - `team` is the home or away side.
* `involves_any(teams)` - any of `teams` is the home or away side.
* `h2h(team1, team2)` - the match is precisely between these two teams.

`players(team=, teams=)` returns every player who appears in the lineups or
in an event, optionally restricted to one team or a list of teams.

`delete_event(event)` and `replace_event(old, new)` locate an event by
equality within `goals`, `cards` or `substitutions` and remove or replace it
in place; both raise `ValueError` if the event isn't found, and
`replace_event` additionally raises `TypeError` if `new` isn't the same
event type as `old`. Passing `new=None` to `replace_event` deletes the event,
which is exactly what `delete_event` does under the hood.

.. note::

   **`Goal.team` is the team credited with the goal, not the scorer's team.**
   For an own goal (`goal_type == "O"`) the scorer belongs to the
   *opposing* team. `Match.event_team(event)` is the single place that
   resolves the team the players involved in an event actually play for,
   flipping it for own goals and passing everything else through unchanged.
   `Match.players()`, `League.update_player()` and `League.player_teams()`
   all call it rather than re-deriving the flip - new code that filters
   players or events by team should do the same, or it will misattribute
   own goals::

       >>> goal.team
       'Team A'
       >>> match.event_team(goal)   # own goal - scorer plays for Team B
       'Team B'

Leagues
-------

`League` fields cover identity and metadata (`league_id`, `name`, `year`,
`start`, `end`, `current`, `coverage`), the season data (`teams`, `rounds`,
`excluded`, `deductions`, `split`), and every `Player` seen in the league,
keyed by `player_id` as a string (`players`). `title` combines `name` with
the season derived from `start`/`end`, e.g. Premiership 2025/26.

`matches(team=, teams=, h2h=)` returns every match across all rounds,
filtered by the same rules as `Match.involves`/`involves_any`/`h2h`, sorted
by date and then home team name. `match_players(team=, teams=, h2h=)` layers
`Match.players` over that filtered match list to return every player
involved, in first-seen order. `head_to_head(teams)` predates
`matches(h2h=...)` and returns the same result; prefer the parameterised
`matches()`/`match_players()` filters for new code.

`events(player)` returns every `EventInfo` (event plus match date, teams and
score) in which `player` is involved across the league, including a
synthesised `LineupStatus` for any match where the player appears in a
lineup but has no other event.

`update_player(old, new, team=)` walks every match and replaces `old` with
`new` wherever it's found - in lineups and in event player references -
optionally restricted to matches where the player features for `team`.
`player_teams(player)` returns every team a player has appeared for across
the season (a player can appear for more than one team in-season, e.g. after
a transfer).

League tables
-------------

`TableRow` accumulates one team's `won`/`drawn`/`lost`/`scored`/`conceded`
plus any `deducted` points, and derives `played` (the sum of `won`, `drawn`
and `lost`), `gd` (`scored` minus `conceded`) and `points`
(`won * 3 + drawn - deducted`). `add_form(result)` appends 'W'/'D'/'L'
to `form`, keeping only the most recent five results.

`as_tuple()` converts a row to a `RowTuple`, a plain `NamedTuple` used as the
return type of `League.table`. `RowTuple` has no `deducted` field of its
own, so `from_tuple()` reconstructs it from `points`
(`deducted = won * 3 + drawn - points`); passing a tuple whose `points` is
higher than `won * 3 + drawn` implies a negative deduction and raises
`ValueError`.

`TableRow` orders by `points`, then `gd`, then `scored`. On a full tie,
`__gt__` reverses the team-name comparison (`self.team < other.team` makes
`self` the *greater* row), which is deliberate: `League.table()` sorts with
`reverse=True`, so the reversed tiebreak is what makes equal teams come
out in ordinary alphabetical order in the final table. Don't "fix" the
apparent inversion.

`table(played=, split_point=, date=)` builds the table from every played
match in date order:

* `played` - if non-zero, stop as soon as every team has played at least
  this many matches.
* `split_point` - if `True`, stop at `League.split` matches instead (used
  internally to compute the split; see below).
* `date` - if given, only include matches on or before this date.

Once any team has played more than `League.split` matches, the table models
the Scottish-style split: the top and bottom halves are frozen by position
at the split point (computed by recursing into `self.table(split_point=True)`)
and each half is then sorted independently. An odd number of teams puts the
extra team into the top half.

Points deductions apply if `Deduction.date` is the empty string (applied
from the start of the season) or falls on or before the last match date
processed - a deduction dated after the table's cutoff is not yet applied.

Date validation
----------------

Dates throughout this package are validated ISO strings, not `date`
objects:

===================== ========================== =================================
Field                 Format                     Notes
===================== ========================== =================================
`Match.kickoff`       yyyy-mm-ddTHH:MM:SS+HH:MM  Offset-aware timestamp; required.
`League.start`/`end`  yyyy-mm-dd                 Zero-padded; required.
`Player.dob`          yyyy-mm-dd or yyyy-m-d     Empty string allowed; normalised
                                                  to zero-padded form.
`Deduction.date`      yyyy-mm-dd                 Empty string allowed (season-start).
===================== ========================== =================================

Each of these layers a real-calendar check on top of its format check, so a
value like month 19 or 29 February in a non-leap year raises `ValueError`
even though it matches the format. Use `Match.date` to get a `datetime.date`
from `kickoff` rather than parsing the string yourself.

Serialisation
-------------

Every model is a standard Pydantic `BaseModel`, so the usual round trip
applies - this is how the models cross between `ilc-api`, `ilc-app` and
`ilc-admin`::

    data = match.model_dump()
    restored = Match.model_validate(data)
    assert restored == match
