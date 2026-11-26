"""Data models for the ILC project.

Pure Pydantic models with no I/O, forming the shared data contract between
ilc-api, ilc-app and ilc-admin.

The models are split across submodules by domain, but every public name is
re-exported here, so import from `ilc_models` directly, e.g.
`from ilc_models import League, Match`.
"""

from .event import (
    BaseEvent,
    Card,
    Event,
    EventTime,
    Goal,
    LineupStatus,
    Substitution,
)
from .league import League, validate_date
from .lineup import Lineup, Lineups
from .match import EventInfo, Match, Score, Teams, validate_kickoff
from .player import BasePlayer, Player, validate_dob
from .table import Deduction, RowTuple, TableRow, validate_deduction_date
from .user import User, UserPublic, validate_created_at, validate_teams

__version__ = "0.3.2"

__all__ = [
    "BaseEvent",
    "BasePlayer",
    "Card",
    "Deduction",
    "Event",
    "EventInfo",
    "EventTime",
    "Goal",
    "League",
    "Lineup",
    "LineupStatus",
    "Lineups",
    "Match",
    "Player",
    "RowTuple",
    "Score",
    "Substitution",
    "TableRow",
    "Teams",
    "User",
    "UserPublic",
    "validate_created_at",
    "validate_date",
    "validate_deduction_date",
    "validate_dob",
    "validate_kickoff",
    "validate_teams",
]
