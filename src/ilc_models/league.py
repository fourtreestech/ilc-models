"""League model."""

import datetime
import math
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

from .event import EventTime, LineupStatus
from .match import EventInfo, Match
from .player import BasePlayer, Player
from .table import Deduction, RowTuple, TableRow


def validate_date(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    """Validate that a value conforms to a valid ISO date string.

    The `Field` pattern on `League.start` and `League.end` bounds
    the string's shape; this additionally confirms the year, month and day
    form a real calendar date. An impossible date, such as month 19 or
    29 February in a non-leap year, will raise a `ValueError`.

    Args:
        value: Date to validate.
        handler: Pydantic validation handler.

    Returns:
        Validated value, unchanged.

    Raises:
        ValueError: If the date is not a real calendar date.
    """
    # Will raise a ValidationError if the Field pattern doesn't match
    date = cast(str, handler(value))

    try:
        datetime.date.fromisoformat(date)
    except ValueError as exc:
        raise ValueError(f"{date} is not a valid ISO date.") from exc

    return date


class League(BaseModel):
    """Represents a League.

    Attributes:
        league_id: API ID of this league.
        name: Name of this league e.g. Premiership.
        year: Year this season starts.
        start: League start date as an ISO format string.
        end: League end date as an ISO format string.
        current: Whether this league is still being played.
        coverage: Coverage available from the API.
        teams: The name of each team in this league (default=[]).
        rounds: This league's rounds, with matches for each round (default={}).
        excluded: Rounds to exclude from import (default=[]).
        deductions: Points deductions applied in this league (default=[]).
        split: Number of matches each team plays before the league splits into
            top and bottom halves; 0 for no split (default=0).
        players: Players who feature in this league, keyed by `player_id` as a string (default={}).
    """

    league_id: PositiveInt
    name: str
    year: PositiveInt
    start: Annotated[
        str,
        Field(pattern=r"^[12][09]\d{2}-[01]\d-[0-3]\d$"),
        WrapValidator(validate_date),
    ]
    end: Annotated[
        str,
        Field(pattern=r"^[12][09]\d{2}-[01]\d-[0-3]\d$"),
        WrapValidator(validate_date),
    ]
    current: bool
    coverage: dict[str, bool]
    teams: list[str] = []
    rounds: dict[str, list[Match]] = {}
    excluded: list[str] = []
    deductions: list[Deduction] = []
    split: NonNegativeInt = 0
    players: dict[str, Player] = {}

    @property
    def title(self) -> str:
        """Title of this league, e.g. Premiership 2023/24.

        Returns:
            Title of the league.
        """
        year1 = int(self.start[:4])
        year2 = int(self.end[:4])
        season = year1 if year1 == year2 else f"{year1}/{year2 % 100}"
        return f"{self.name} {season}"

    def matches(
        self,
        team: Optional[str] = None,
        teams: Optional[list[str]] = None,
        h2h: Optional[tuple[str, str]] = None,
        player: Optional[BasePlayer] = None,
    ) -> list[Match]:
        """Get the matches in this league.

        If `team` is given, return only matches involving this team.
        If `teams` is given, return only matches involving one of these teams.
        If `h2h` is given, return only matches between these two teams.
        If `player` is given, return only matches featuring this player.

        The filters are alternatives: if more than one is given only the first
        applies, in the order `team`, `teams`, `h2h`, `player`.

        Args:
            team: Get matches for this team (default=None).
            teams: Get matches involving any of these teams (default=None).
            h2h: Get matches between these two teams (default=None).
            player: Get matches featuring this player (default=None).

        Returns:
            Matches sorted by date and then home team.
        """
        # fn is the function that determines whether to include this match
        if team:
            fn = lambda m: m.involves(team)
        elif teams:
            fn = lambda m: m.involves_any(teams)
        elif h2h:
            fn = lambda m: m.h2h(*h2h)
        elif player:
            fn = lambda m: player in m.players()
        else:
            fn = lambda _: True

        # Extract matches that pass the fn test
        _matches = []
        for m in self.rounds.values():
            for match in m:
                if fn(match):
                    _matches.append(match)

        # Sort and return
        _matches.sort(key=attrgetter("teams.home"))
        _matches.sort(key=attrgetter("date"))
        return _matches

    def events(self, player: BasePlayer) -> list[EventInfo]:
        """Get all events in this league in which a player is involved.

        Also includes a `LineupStatus` event for any matches
        which include the player in their lineup.

        Args:
            player: Find events featuring this player.

        Returns:
            The events in this league involving the player.
        """
        e = []
        for match in self.matches(player=player):
            # Find player in lineups
            status = None
            for team, lineup in zip(
                (match.teams.home, match.teams.away),
                (match.lineups.home, match.lineups.away),
                strict=False,
            ):
                if player in (p[1] for p in lineup.starting):
                    status = LineupStatus(
                        team=team,
                        time=EventTime(minutes=1),
                        status="starting",
                        player=player,
                    )
                elif player in (p[1] for p in lineup.subs):
                    status = LineupStatus(
                        team=team,
                        time=EventTime(minutes=1),
                        status="sub",
                        player=player,
                    )
                if status:
                    e.append(
                        EventInfo(
                            date=match.date,
                            teams=match.teams,
                            score=match.score,
                            event=status,
                        )
                    )
                    break

            # Find player in events
            for event in match.events():
                if player in event.players():
                    e.append(
                        EventInfo(
                            date=match.date,
                            teams=match.teams,
                            score=match.score,
                            event=event,
                        )
                    )
        return e

    def update_player(
        self, old: BasePlayer, new: BasePlayer, team: Optional[str] = None
    ) -> None:
        """Replace all occurrences of `old` with `new`.

        Searches all lineups and events in this league and
        replaces all occurrences of `old` with `new`.

        If `team` is given, replace only occurrences where the player
        features for `team`.

        Args:
            old: Player to be replaced.
            new: New player details.
            team: If given, replace only where the player features for this
                team (default=None).
        """
        for matches in self.rounds.values():
            for match in matches:
                if (team is None or match.involves(team)) and old in match.players():
                    lineups = []
                    if team is None or team == match.teams.home:
                        lineups.append(match.lineups.home)
                    if team is None or team == match.teams.away:
                        lineups.append(match.lineups.away)

                    # Update lineups
                    for lineup in lineups:
                        for plist in (
                            lineup.starting,
                            lineup.subs,
                        ):
                            for n, player in enumerate(plist):
                                if player[1] == old:
                                    plist[n] = (player[0], new)
                                    break
                            else:
                                continue
                            break

                    # Update events
                    for goal in match.goals:
                        if (
                            team is None or match.event_team(goal) == team
                        ) and goal.scorer == old:
                            goal.scorer = new

                    for card in match.cards:
                        if (team is None or card.team == team) and card.player == old:
                            card.player = new

                    for sub in match.substitutions:
                        if team is None or sub.team == team:
                            if sub.player_on == old:
                                sub.player_on = new
                            elif sub.player_off == old:
                                sub.player_off = new

    def player_teams(self, player: BasePlayer) -> list[str]:
        """Get all the teams a player features in during this season.

        Args:
            player: Find teams this player plays for.

        Returns:
            The teams the player plays for in this league.
        """
        teams = set()

        # Check each match as a player may play for more than
        # one team during a single season
        for match in self.matches(player=player):
            if team := match.played_for(player):
                teams.add(team)

        return list(teams)

    def match_players(
        self,
        team: Optional[str] = None,
        teams: Optional[list[str]] = None,
        h2h: Optional[tuple[str, str]] = None,
    ) -> list[BasePlayer]:
        """Get all players involved in at least one match in this league.

        If `team` is given return only players who have featured for this team.
        If `teams` is given return only players who have featured for one of these teams.
        If `h2h` is given return only players who featured in a match between these two teams.

        The match filter follows the precedence described in `matches`, and
        `team` or `teams` also restrict which players are returned from each match.

        Args:
            team: Get players who played for this team (default=None).
            teams: Get players who played for any of these teams (default=None).
            h2h: Get players who played in a match between these two teams
                (default=None).

        Returns:
            All players involved in a match.
        """
        players = []
        for match in self.matches(team=team, teams=teams, h2h=h2h):
            for p in match.players(team=team, teams=teams):
                if p not in players:
                    players.append(p)
        return players

    def table(
        self,
        played: int = 0,
        split_point: bool = False,
        date: Optional[datetime.date] = None,
    ) -> list[RowTuple]:
        """Get the league table.

        Returns the league table as a list of `RowTuple` items,
        ordered by league position.

        If `played` is non-zero the table will be returned at
        the first point at which all teams have played at least
        `played` matches.

        If `split_point` is `True` the table will be returned
        at the league's split point.

        If `date` is not `None` the table will be returned
        at the given date, i.e. taking account only of matches
        where the date is earlier than or equal to `date`.

        Points deductions with no date always apply. A dated deduction
        applies only if its date is on or before the last match counted
        (or on or before `date`, if that stopped the table early).

        Args:
            played: If non-zero, get table after this number of games (default=0).
            split_point: If True get the table at the split point (default=False).
            date: If given, get the league table on this date (default=None).

        Returns:
            The league table as a list of `RowTuple` items, ordered by position.
        """
        # Create rows
        rows = {team: TableRow(team=team) for team in self.teams}

        # Get table at split point
        if split_point:
            played = self.split

        # Retain the date of the last match processed to manage deductions
        last_date = None

        # Add matches
        for match in (m for m in self.matches() if m.played):
            # Check for date
            if date is not None and match.date > date:
                last_date = date
                break

            # Get rows
            home = rows[match.teams.home]
            away = rows[match.teams.away]

            # W/D/L
            if match.score.home > match.score.away:
                home.won += 1
                away.lost += 1
                home.add_form("W")
                away.add_form("L")
            elif match.score.home < match.score.away:
                home.lost += 1
                away.won += 1
                home.add_form("L")
                away.add_form("W")
            else:
                home.drawn += 1
                away.drawn += 1
                home.add_form("D")
                away.add_form("D")

            # Goals
            home.scored += match.score.home
            home.conceded += match.score.away
            away.scored += match.score.away
            away.conceded += match.score.home

            # Retain date
            last_date = match.date

            # Check if all teams have played the required number of games
            if played and all(row.played >= played for row in rows.values()):
                break

        # Handle deductions
        for deduction in self.deductions:
            if not deduction.date or (
                last_date is not None
                and datetime.date.fromisoformat(deduction.date) <= last_date
            ):
                rows[deduction.team].deducted += deduction.points

        # Handle split
        if (
            not split_point
            and self.split
            and any(row.played > self.split for row in rows.values())
        ):
            # Post-split - find the positions at the split point
            split = self.table(split_point=True)
            order = [row[0] for row in split]

            # Get the top and bottom half teams at the split
            # (odd number puts the extra team into the top half)
            team_count = math.ceil(len(rows) / 2)
            top_teams = order[:team_count]
            bottom_teams = order[team_count:]

        else:
            # Pre-split - just put all teams into the top section
            top_teams = list(rows.keys())
            bottom_teams = []

        # Sort top and bottom separately
        top = sorted((rows[team] for team in top_teams), reverse=True)
        bottom = sorted((rows[team] for team in bottom_teams), reverse=True)
        return [row.as_tuple() for row in top] + [row.as_tuple() for row in bottom]

    def head_to_head(self, teams: tuple[str, str]) -> list[Match]:
        """Get all matches played between two teams.

        Args:
            teams: Teams to query.

        Returns:
            All matches between these two teams.
        """
        return [match for match in self.matches(teams[0]) if match.involves(teams[1])]

    def __str__(self) -> str:  # pragma: no cover
        """Return the league's `title`.

        Returns:
            The league's `title`.
        """
        return self.title
