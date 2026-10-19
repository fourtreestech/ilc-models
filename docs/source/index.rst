ilc-models
==========

**Data models for the *ILC* project**

`ilc-models` is a set of pure Pydantic v2 models with no I/O. It forms the
shared data contract used across the `ilc-api`, `ilc-app` and `ilc-admin`
repositories - a `League` of `Match` objects, each with its `Lineups`,
`Goal`/`Card`/`Substitution` events, and the `TableRow` results computed
from them, plus `User` and `UserPublic` models for accounts. Its only
dependencies are `pydantic` (with the email extra) and `argon2-cffi`, which
`User` uses to hash passwords.

::

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

For more detail see the :doc:`usage` documentation.

Installation
------------

`ilc-models` requires Python 3.12 or later. To install, run::

    (.venv) $ pip install ilc-models

Or with `uv <https://docs.astral.sh/uv/>`_::

    $ uv add ilc-models

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   usage
   api
