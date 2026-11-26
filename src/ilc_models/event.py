"""Match event models."""

import abc
import functools
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from .player import BasePlayer


@functools.total_ordering
class EventTime(BaseModel):
    """The time an event occurred during a match.

    Attributes:
        minutes: Minutes elapsed (1-120).
        plus: Additional time minutes i.e. after 45, 90 etc. (default=0).
    """

    minutes: int = Field(gt=0, le=120)
    plus: NonNegativeInt = 0

    @model_validator(mode="after")
    def check_valid_time(self) -> Self:
        """Check the `minutes` field is valid if `plus` is non-zero.

        Returns:
            `self`, unchanged.

        Raises:
            ValueError: If `plus` is non-zero and `minutes` is not one of 45,
                90, 105 or 120, i.e. additional time is only valid at the end
                of a half.
        """
        if self.plus != 0 and self.minutes not in (45, 90, 105, 120):
            raise ValueError("Additional time is only valid at the end of a half")

        return self

    def __eq__(self, other: Any) -> bool:
        """Return True if `self` and `other` are equal.

        Args:
            other: Time to compare to.

        Returns:
            `True` if the times are equal.
        """
        try:
            return (self.minutes, self.plus) == (other.minutes, other.plus)
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __gt__(self, other: Any) -> bool:
        """Return True if `self` is greater than `other`.

        Args:
            other: Time to compare to.

        Returns:
            `True` if `self` is greater than `other`.
        """
        try:
            return (self.minutes, self.plus) > (other.minutes, other.plus)
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __str__(self) -> str:
        """Return the event time as a string, e.g. `90+3'`.

        Returns:
            The event time as a string.
        """
        p = f"+{self.plus}" if self.plus else ""
        return f"{self.minutes}{p}'"


class BaseEvent(BaseModel, abc.ABC):
    """Abstract base class for events.

    Attributes:
        team: Team this event relates to.
        time: Event time.
    """

    team: str
    time: EventTime

    def time_str(self) -> str:
        """Return the event time as a string.

        Returns:
            The event time as a string.
        """
        return str(self.time)

    @abc.abstractmethod
    def players(self) -> list[BasePlayer]:  # pragma: no cover
        """Get the players involved in this event.

        Returns:
            The players involved in this event.
        """
        pass


class Goal(BaseEvent):
    """Represents a goal.

    The inherited `team` is the team credited with the goal. For an own goal
    this is the opposite team to the scorer's; see `Match.event_team`.

    Attributes:
        event_type: The literal string 'goal'.
        goal_type: One of 'N' (normal goal), 'O' (own goal), 'P' (penalty) (default='N').
        scorer: Goal scorer.
    """

    event_type: Literal["goal"] = Field(default="goal", frozen=True)
    goal_type: Literal["N", "O", "P"] = "N"
    scorer: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event.

        Returns:
            The goal scorer.
        """
        return [self.scorer]


class Card(BaseEvent):
    """Represents a red or yellow card.

    Attributes:
        event_type: The literal string 'card'.
        color: One of 'R' (red card), 'Y' (yellow card).
        player: Player receiving the card.
    """

    event_type: Literal["card"] = Field(default="card", frozen=True)
    color: Literal["Y", "R"]
    player: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event.

        Returns:
            The player who received the card.
        """
        return [self.player]


class Substitution(BaseEvent):
    """Represents a substitution.

    Attributes:
        event_type: The literal string 'sub'.
        player_on: Player entering the field.
        player_off: Player leaving the field.
    """

    event_type: Literal["sub"] = Field(default="sub", frozen=True)
    player_on: BasePlayer
    player_off: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event.

        Returns:
            The player coming off followed by the player going on.
        """
        return [self.player_off, self.player_on]


class LineupStatus(BaseEvent):
    """Whether a player is in the starting lineup or on the bench.

    Attributes:
        event_type: The literal string 'status'.
        status: One of 'starting' or 'sub'.
        player: Player involved.
    """

    event_type: Literal["status"] = Field(default="status", frozen=True)
    status: Literal["starting", "sub"]
    player: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event.

        Returns:
            The player whose lineup status is being reported.
        """
        return [self.player]


type Event = Goal | Card | Substitution | LineupStatus
"""Union of all event types that can occur in a `Match`."""
