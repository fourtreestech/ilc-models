"""Match models."""

import datetime
from operator import attrgetter
from typing import Annotated, Any, Optional, cast

from pydantic import (
    BaseModel,
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)

from .event import Card, Event, Goal, Substitution
from .lineup import Lineups
from .player import BasePlayer


class Teams(BaseModel):
    """The teams in a match.

    Attributes:
        home: Home team.
        away: Away team.
    """

    home: str
    away: str


class Score(BaseModel):
    """Match score.

    Attributes:
        home: Home team score (default=0).
        away: Away team score (default=0).
    """

    home: NonNegativeInt = 0
    away: NonNegativeInt = 0


def validate_kickoff(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    """Validate that a value conforms to a valid kickoff string.

    The `Field` pattern on `Match.kickoff` bounds the string's shape;
    this additionally confirms the year, month and day form a real calendar
    date. An impossible date, such as month 19 or 29 February in a non-leap
    year, will raise a `ValueError`.

    Args:
        value: Kickoff datetime to validate.
        handler: Pydantic validation handler.

    Returns:
        Validated value, unchanged.

    Raises:
        ValueError: If the date is not a real calendar date.
    """
    # Will raise a ValidationError if the Field pattern doesn't match
    kickoff = cast(str, handler(value))

    try:
        datetime.datetime.fromisoformat(kickoff)
    except ValueError as exc:
        raise ValueError(f"{kickoff} is not a valid ISO date.") from exc

    return kickoff


class Match(BaseModel):
    """Represents a match.

    Attributes:
        match_id: API ID of this match.
        kickoff: Kickoff as an offset-aware ISO 8601 timestamp,
            e.g. '2025-08-09T15:00:00+01:00'.
        round: Round this match is part of.
        teams: Teams involved in this match.
        status: Match status code from the API, e.g. 'NS', 'FT', 'AET' or 'PEN'
            (see `played`).
        score: Score in this match (default=0-0).
        goals: Detail of goals scored in the match (default=[]).
        cards: Detail of cards shown in the match (default=[]).
        substitutions: Detail of substitutions made in the match (default=[]).
        lineups: Match lineups (default=`Lineups()`).
    """

    match_id: PositiveInt
    kickoff: Annotated[
        str,
        Field(
            pattern=r"^[12][09]\d{2}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d[+-][01]\d:[0-5]\d$"
        ),
        WrapValidator(validate_kickoff),
    ]
    round: str
    teams: Teams
    status: str
    score: Score = Score()
    goals: list[Goal] = []
    cards: list[Card] = []
    substitutions: list[Substitution] = []
    lineups: Lineups = Lineups()

    @property
    def played(self) -> bool:
        """Return True if this match has been played to a finish.

        Returns:
            `True` if `status` is one of 'FT', 'AET' or 'PEN'.
        """
        return self.status in ("FT", "AET", "PEN")

    @property
    def date(self) -> datetime.date:
        """Return the date this match kicked off.

        Returns:
            The date portion of `kickoff`.
        """
        return datetime.datetime.fromisoformat(self.kickoff).date()

    def involves(self, team: str) -> bool:
        """Return True if `team` is involved in this match.

        Args:
            team: Team to query.

        Returns:
            `True` if `team` is involved in this match, i.e. either as
            the home team or the away team.
        """
        return self.teams.home == team or self.teams.away == team

    def involves_any(self, teams: list[str]) -> bool:
        """Return True if any of `teams` is involved in this match.

        Args:
            teams: Teams to query.

        Returns:
            `True` if any of `teams` are involved in this match, i.e.
            either as the home team or the away team.
        """
        return any(self.involves(team) for team in teams)

    def h2h(self, team1: str, team2: str) -> bool:
        """Return True if the match is a head to head between these two teams.

        Args:
            team1: First team.
            team2: Second team.

        Returns:
            `True` if the match is between the two teams, `False` otherwise.
        """
        return (self.teams.home == team1 and self.teams.away == team2) or (
            self.teams.home == team2 and self.teams.away == team1
        )

    def events(self) -> list[Event]:
        """Get all events in this match in chronological order.

        Returns:
            The combined list of goals, cards and subs in the match.
        """
        e = self.goals + self.cards + self.substitutions
        return sorted(e, key=attrgetter("time"))

    def players(
        self, team: Optional[str] = None, teams: Optional[list[str]] = None
    ) -> list[BasePlayer]:
        """Get all players involved in this match.

        If `team` is provided return only players from the team specified.
        If `teams` is provided return only players from one of the teams specified.
        If both are provided, `teams` takes precedence and `team` is ignored.

        Args:
            team: Return only players from this team (default=None).
            teams: Return only players from these teams (default=None).

        Returns:
            Players involved in the match.
        """
        # Manage team param
        if not teams and team:
            teams = [team]

        # Get players from lineups
        if teams:
            # Neither team - just return empty list
            if self.teams.home not in teams and self.teams.away not in teams:
                return []

            # Add lineups
            p = []
            if self.teams.home in teams:
                p += self.lineups.home.players()
            if self.teams.away in teams:
                p += self.lineups.away.players()
        else:
            p = self.lineups.players()

        # Add players from events
        for event in self.events():
            if not teams or self.event_team(event) in teams:
                for player in event.players():
                    if player not in p:
                        p.append(player)
        return p

    def played_for(self, player: BasePlayer) -> str:
        """Get the team this player plays for in this match.

        Checks lineups and events for the player and returns
        the name of the team they play for in the match, or
        empty string if the player isn't found.

        Args:
            player: Player to find the team for.

        Returns:
            The team the player played for in the match.
        """
        for team, lineup in zip(
            (self.teams.home, self.teams.away),
            (self.lineups.home, self.lineups.away),
            strict=False,
        ):
            if player in lineup.players():
                return team

        for event in self.events():
            if player in event.players():
                return self.event_team(event)

        return ""

    def event_team(self, event: Event) -> str:
        """Get the team the players involved in `event` play for.

        This is `event.team` for every event except an own goal, where
        `Goal.team` is the team credited with the goal and the scorer
        therefore plays for the opposing team.

        Args:
            event: Event to find the team for.

        Returns:
            The team the players involved in the event play for.
        """
        if event.event_type == "goal" and event.goal_type == "O":
            return self.teams.away if event.team == self.teams.home else self.teams.home
        return event.team

    def delete_event(self, event: Event) -> bool:
        """Delete an event from this match.

        Args:
            event: Event to delete.

        Returns:
            `True` if the event was successfully deleted.

        Raises:
            ValueError: If the event is not found in the match.
        """
        return self.replace_event(event, None)

    def replace_event(self, old: Event, new: Optional[Event]) -> bool:
        """Replace `old` with `new`.

        If `new` is `None` the event will be deleted instead.

        Args:
            old: Event to replace.
            new: New event (`None` to delete the event).

        Returns:
            `True` if the event was successfully replaced or deleted.

        Raises:
            ValueError: If the event is not found in the match.
            TypeError: If `old` and `new` are not the same event type.
        """
        n = -1
        match old:
            case Goal():
                for i, goal in enumerate(self.goals):
                    if goal == old:
                        n = i
                        break
                if n != -1:
                    if new is None:
                        del self.goals[n]
                    elif isinstance(new, Goal):
                        self.goals[n] = new
                    else:
                        raise TypeError("new should be the same event type as old")

            case Card():
                for i, card in enumerate(self.cards):
                    if card == old:
                        n = i
                        break
                if n != -1:
                    if new is None:
                        del self.cards[n]
                    elif isinstance(new, Card):
                        self.cards[n] = new
                    else:
                        raise TypeError("new should be the same event type as old")

            case Substitution():
                for i, sub in enumerate(self.substitutions):
                    if sub == old:
                        n = i
                        break
                if n != -1:
                    if new is None:
                        del self.substitutions[n]
                    elif isinstance(new, Substitution):
                        self.substitutions[n] = new
                    else:
                        raise TypeError("new should be the same event type as old")

        if n == -1:
            raise ValueError("Event not found in Match")
        return True

    def __str__(self) -> str:
        """Return the match as a string, e.g. 'Team A 2 - 1 Team B'.

        Unplayed matches are shown without a score, e.g. 'Team A vs Team B'.

        Returns:
            The match as a string.
        """
        if self.played:
            return f"{self.teams.home} {self.score.home} - {self.score.away} {self.teams.away}"
        return f"{self.teams.home} vs {self.teams.away}"


class EventInfo(BaseModel):
    """Event data with match info added.

    Attributes:
        date: Date of match.
        teams: Teams involved in the match.
        score: Match score.
        event: Event info.
    """

    date: datetime.date
    teams: Teams
    score: Score
    event: Event
