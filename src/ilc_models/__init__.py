"""Data models for the ILC project"""

import abc
import datetime
import functools
import re
from operator import attrgetter, itemgetter
from typing import Annotated, Any, Literal, Optional, Self, cast

from pydantic import (
    BaseModel,
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    model_validator,
)

__version__ = "0.1.7"

type RowTuple = tuple[str, int, int, int, int, int, int, int, int]
"""Type for a single row of a league table."""


class BasePlayer(BaseModel):
    """Basic level of player details.

    :param player_id: ID of this player in the API
    :type player_id: int
    :param name: Player's full (display) name
    :type name: str
    """

    player_id: int
    name: str

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        """Equality comparison.

        If `player_id` is non-zero the equality comparison will return `True`
        if player IDs match i.e. ignores different values of `name`.
        This is because there are often slight variances in the API between player names
        in events and in downloaded player data, which would otherwise cause mismatches
        when finding players in events.

        If `player_id` is zero in both `self` and `other` then the player names
        will also be compared.
        """
        try:
            if self.player_id == 0 and other.player_id == 0:
                return self.name == other.name
            return self.player_id == other.player_id

        except AttributeError:  # pragma: no cover
            return NotImplemented


def validate_dob(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    """Validate that a value conforms to a valid DOB string.

    Allows empty string, yyyy-m-d and yyyy-mm-dd.
    Any other format will raise a :exc:`ValueError`.

    :param value: DOB to validate
    :type value: :class:`typing.Any`
    :param handler: Pydantic validation handler
    :type handler: :class:`pydantic.ValidatorFunctionWrapHandler`
    :returns: Validated value in `yyyy-mm-dd` format
    :rtype: str
    :raises: :exc:`ValueError` if format is invalid
    """
    # Will raise a ValidationError for a non-string
    dob = cast(str, handler(value))

    # Accept the empty string
    if dob == "":
        return dob

    # yyyy-mm-dd regex
    pattern = re.compile(r"[12][09]\d{2}-[01]\d-[0-3]\d$")

    # Matches - return as validated
    if re.match(pattern, dob):
        return dob

    # Allow for missing zeros
    pattern = re.compile(r"[12][09]\d{2}-\d{1,2}-\d{1,2}$")
    if not re.match(pattern, dob):
        raise ValueError(f"{dob} is not a valid ISO date format.")

    # Convert to yyyy-mm-dd and return
    y, m, d = (int(n) for n in dob.split("-"))
    return f"{y}-{m:02}-{d:02}"


class Player(BasePlayer):
    """Full player details.

    :param first_name: Player's first name
    :type first_name: str
    :param last_name: Player's last name
    :type last_name: str
    :param dob: Player's date of birth in ISO (yyyy-mm-dd) format
    :type dob: str
    :param nationality: Player's nationality
    :type nationality: str
    """

    first_name: str
    last_name: str
    dob: Annotated[str, WrapValidator(validate_dob)]
    nationality: str

    @property
    def base_player(self) -> BasePlayer:
        """Return a `BasePlayer` object corresponding to this `Player`.

        :returns: The `BasePlayer` corresponding to this `Player`
        :rtype: :class:`BasePlayer`
        """
        return BasePlayer(player_id=self.player_id, name=self.name)


class Lineup(BaseModel):
    """Lineup for one team.

    Each lineup entry is an (int, BasePlayer) tuple, with the int
    being the player's shirt number if supplied (0 if not).

    :param starting: Starting XI (default=[])
    :type starting: list[tuple[int, BasePlayer]]
    :param subs: Substitutes (default=[])
    :type subs: list[tuple[int, BasePlayer]]
    """

    starting: list[tuple[int, BasePlayer]] = Field(max_length=11, default=[])
    subs: list[tuple[int, BasePlayer]] = []

    def __bool__(self) -> bool:
        """Returns True if this lineup is populated with players."""
        return len(self.starting) + len(self.subs) > 0

    def sort(self):
        """Sorts the lineup.

        Each part of the lineup is sorted by shirt number, except
        for the first item in the starting lineup which is
        assumed to be the goalkeeper and is left as the first item.
        """
        self.starting = self.starting[:1] + sorted(self.starting[1:], key=itemgetter(0))
        self.subs.sort(key=itemgetter(0))

    def players(self) -> list[BasePlayer]:
        """Returns all players in this lineup"""
        return [p[1] for p in self.starting] + [p[1] for p in self.subs]

    def __len__(self) -> int:
        """Returns the total number of players in this lineup"""
        return len(self.starting) + len(self.subs)


class Lineups(BaseModel):
    """Match lineups for home and away teams.

    :param home: Home lineup (default=Lineup())
    :type home: :class:`Lineup`
    :param away: Away lineup (default=Lineup())
    :type away: :class:`Lineup`
    """

    home: Lineup = Lineup()
    away: Lineup = Lineup()

    def __bool__(self) -> bool:
        """Returns True if either lineup is populated with players."""
        return bool(self.home) or bool(self.away)

    def sort(self):
        """Sort the lineups.

        Each part of the lineup is sorted by shirt number, except
        for the first item in the starting lineup which is
        assumed to be the goalkeeper and is left as the first item.
        """
        self.home.sort()
        self.away.sort()

    def players(self) -> list[BasePlayer]:
        """Returns all players in this lineup"""
        return self.home.players() + self.away.players()

    def __len__(self) -> int:
        """Returns the total number of players in these lineups"""
        return len(self.home) + len(self.away)


@functools.total_ordering
class EventTime(BaseModel):
    """The time an event occurred during a match.

    :param minutes: Minutes elapsed (1-120)
    :type minutes: int
    :param plus: Additional time minutes i.e. after 45, 90 etc. (default=0)
    :type plus: int
    """

    minutes: int = Field(gt=0, le=120)
    plus: NonNegativeInt = 0

    @model_validator(mode="after")
    def check_valid_time(self) -> Self:
        """Checks the `minutes` field is valid if `plus` is non-zero"""
        if self.plus != 0 and self.minutes not in (45, 90, 105, 120):
            raise ValueError("Additional time is only valid at the end of a half")

        return self

    def __eq__(self, other: Any) -> bool:
        """Returns True if `self` and `other` are equal.

        :param other: Time to compare to
        :type other: Any
        :returns: `True` if the times are equal
        :rtype: bool
        """
        try:
            return (self.minutes, self.plus) == (other.minutes, other.plus)
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __gt__(self, other: Any) -> bool:
        """Returns True if `self` is greater than `other.

        :param other: Time to compare to
        :type other: Any
        :returns: `True` if `self` is greater than `other`
        :rtype: bool
        """
        try:
            return (self.minutes, self.plus) > (other.minutes, other.plus)
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __str__(self) -> str:
        """The event time in str format"""
        p = f"+{self.plus}" if self.plus else ""
        return f"{self.minutes}{p}'"


class BaseEvent(BaseModel, abc.ABC):
    """Abstract base class for events.

    :param team: Team this event relates to
    :type team: str
    :param time: Event time
    :type time: :class:`EventTime`
    """

    team: str
    time: EventTime

    def time_str(self) -> str:
        """The event time in str format"""
        return str(self.time)

    @abc.abstractmethod
    def players(self) -> list[BasePlayer]:  # pragma: no cover
        """Get the players involved in this event"""
        pass


class Goal(BaseEvent):
    """Represents a goal.

    :param event_type: The literal string 'goal'
    :type event_type: str
    :param goal_type: One of 'N' (normal goal), 'O' (own goal), 'P' (penalty) (default='N')
    :type goal_type: str
    :param scorer: Goal scorer
    :type scorer: :class:`BasePlayer`
    """

    event_type: Literal["goal"] = Field(default="goal", frozen=True)
    goal_type: Literal["N", "O", "P"] = "N"
    scorer: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event"""
        return [self.scorer]


class Card(BaseEvent):
    """Represents a red or yellow card.

    :param event_type: The literal string 'card'
    :type event_type: str
    :param color: One of 'R' (red card), 'Y' (yellow card)
    :type color: str
    :param player: Player receiving the card
    :type player: :class:`BasePlayer`
    """

    event_type: Literal["card"] = Field(default="card", frozen=True)
    color: Literal["Y", "R"]
    player: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event"""
        return [self.player]


class Substitution(BaseEvent):
    """Represents a substitution.

    :param event_type: The literal string 'sub'
    :type event_type: str
    :param player_on: Player entering the field
    :type player_on: :class:`BasePlayer`
    :param player_off: Player leaving the field
    :type player_off: :class:`BasePlayer`
    """

    event_type: Literal["sub"] = Field(default="sub", frozen=True)
    player_on: BasePlayer
    player_off: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event"""
        return [self.player_off, self.player_on]


class LineupStatus(BaseEvent):
    """Whether a player is in the starting lineup or on the bench.

    :param event_type: The literal string 'status'
    :type event_type: str
    :param status: One of 'starting' or 'sub'
    :type status: str
    :param player: Player involved
    :type player: :class:`BasePlayer`
    """

    event_type: Literal["status"] = Field(default="status", frozen=True)
    status: Literal["starting", "sub"]
    player: BasePlayer

    def players(self) -> list[BasePlayer]:
        """Get the players involved in this event"""
        return [self.player]


type Event = Goal | Card | Substitution | LineupStatus


class Teams(BaseModel):
    """The teams in a match.

    :param home: Home team
    :type home: str
    :param away: Away team
    :type away: str
    """

    home: str
    away: str


class Score(BaseModel):
    """Match score.

    :param home: Home team score (default=0)
    :type home: int
    :param away: Away team score (default=0)
    :type away: int
    """

    home: NonNegativeInt = 0
    away: NonNegativeInt = 0


class Match(BaseModel):
    """Represents a match.

    :param match_id: API ID of this match
    :type match_id: int
    :param kickoff: Date of match in ISO string format
    :type kickoff: str
    :param round: Round this match is part of
    :type round: str
    :param teams: Teams involved in this match
    :type teams: :class:`Teams`
    :param status: Match status
    :type status: str
    :param score: Score in this match (default=0-0)
    :type score: :class:`Score`
    :param goals: Detail of goals scored in the match
    :type goals: list[:class:`Goal`]
    :param cards: Detail of cards shown in the match
    :type cards: list[:class:`Card`]
    :param substitutions: Detail of substitutions made in the match
    :type substitutions: list[:class:`Substitution`]
    :param lineups: Match lineups
    :type lineups: :class:`Lineups`
    """

    match_id: PositiveInt
    kickoff: str = Field(
        pattern=r"^[12][09]\d{2}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d[+-][01]\d:[0-5]\d$"
    )
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
        return self.status in ("FT", "AET", "PEN")

    @property
    def date(self) -> datetime.date:
        return datetime.datetime.fromisoformat(self.kickoff).date()

    def involves(self, team: str) -> bool:
        """Returns ``True`` if ``team`` is involved in this match.

        :param team: Team to query
        :type team: str
        :returns: ``True`` if ``team`` is involved in this match, i.e.
                  either as the home team or the away team
        :rtype: bool
        """
        return self.teams.home == team or self.teams.away == team

    def events(self) -> list[Event]:
        """Returns all events in this match in chronological order.

        :returns: The combined list of goals, cards and subs in the match
        :rtype: list[:class:`Event`]
        """
        e = self.goals + self.cards + self.substitutions
        return sorted(e, key=attrgetter("time"))

    def players(self) -> list[BasePlayer]:
        """Returns all players involved in this match"""
        p = self.lineups.players()
        for event in self.events():
            for player in event.players():
                if player not in p:
                    p.append(player)
        return p

    def delete_event(self, event: Event) -> bool:
        """Delete an event from this match.

        :param event: Event to delete
        :type event: :class:`Event`
        :returns: `True` if the event was successfully deleted
        :raises: :exc:`ValueError` if the event is not found in the match
        """
        return self.replace_event(event, None)

    def replace_event(self, old: Event, new: Optional[Event]) -> bool:
        """Replace `old` with `new`. If `new` is `None` the event will be deleted.

        :param old: Event to replace
        :type old: :class:`Event`
        :param new: New event (`None` to delete the event)
        :type new: :class:`Event` | None
        :returns: `True` if the event was successfully replaced or deleted
        :raises: :exc:`ValueError` if the event is not found in the match
        :raises: :exc:`TypeError` if `old` and `new` are not the same event type
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
        if self.played:
            return f"{self.teams.home} {self.score.home} - {self.score.away} {self.teams.away}"
        return f"{self.teams.home} vs {self.teams.away}"


@functools.total_ordering
class TableRow(BaseModel):
    """A row in a league table.

    :param team: Team name
    :type team: str
    :param won: Matches won (default=0)
    :type won: int
    :param drawn: Matches drawn (default=0)
    :type drawn: int
    :param lost: Matches lost (default=0)
    :type lost: int
    :param scored: Goals scored (default=0)
    :type scored: int
    :param conceded: Goals conceded (default=0)
    :type conceded: int
    """

    team: str
    won: NonNegativeInt = 0
    drawn: NonNegativeInt = 0
    lost: NonNegativeInt = 0
    scored: NonNegativeInt = 0
    conceded: NonNegativeInt = 0
    deducted: NonNegativeInt = 0

    @property
    def played(self) -> int:
        """Matches played.

        :returns: The total number of matches played
        :rtype: int
        """
        return self.won + self.drawn + self.lost

    @property
    def gd(self) -> int:
        """Goal difference.

        :returns: The goal difference, i.e. goals scored minus goals conceded
        :rtype: int
        """
        return self.scored - self.conceded

    @property
    def points(self) -> int:
        """Total points gained.

        :returns: The total number of points gained
        :rtype: int
        """
        return self.won * 3 + self.drawn - self.deducted

    def as_tuple(self) -> RowTuple:
        """Returns this row as a tuple.

        Elements are: (team, played, won, drawn, lost, scored, conceded, gd, points)

        :returns: This row as a tuple
        :rtype: :type:`RowTuple`
        """
        return (
            self.team,
            self.played,
            self.won,
            self.drawn,
            self.lost,
            self.scored,
            self.conceded,
            self.gd,
            self.points,
        )

    @classmethod
    def from_tuple(cls, row_tuple: RowTuple) -> "TableRow":
        """Creates a `TableRow` instance from a `RowTuple`.

        :param row_tuple: Source tuple
        :type row_tuple: :class:`RowTuple`
        :returns: Newly created `TableRow`
        :rtype: :class:`TableRow`
        """
        return cls(
            team=row_tuple[0],
            won=row_tuple[2],
            drawn=row_tuple[3],
            lost=row_tuple[4],
            scored=row_tuple[5],
            conceded=row_tuple[6],
        )

    def __eq__(self, other: Any) -> bool:
        """Returns True if `self` and `other` are equal.

        :param other: Row to compare to
        :type other: :class:`ilc_models.TableRow`
        :returns: `True` if the rows are equal
        :rtype: bool
        """
        try:
            return (self.points, self.gd, self.scored, self.team) == (
                other.points,
                other.gd,
                other.scored,
                other.team,
            )
        except AttributeError:
            return NotImplemented

    def __gt__(self, other: Any) -> bool:  # pragma: no cover
        """Returns True if `self` is greater than `other.

        Ordering is by points, GD and goals scored.
        If all are equal, team name will be compared
        in reverse alphabetical order so that a sorted league table
        will be ordered alphabetically.

        :param other: Row to compare to
        :type other: :class:`ilc_models.TableRow`
        :returns: `True` if `self` is greater than `other`
        :rtype: bool
        """
        try:
            if (self.points, self.gd, self.scored) == (
                other.points,
                other.gd,
                other.scored,
            ):
                return self.team < other.team
            return (self.points, self.gd, self.scored) > (
                other.points,
                other.gd,
                other.scored,
            )
        except AttributeError:
            return NotImplemented

    def __str__(self) -> str:
        return " ".join(
            (
                self.team,
                f"P{self.played}",
                f"W{self.won}",
                f"D{self.drawn}",
                f"L{self.lost}",
                f"F{self.scored}",
                f"A{self.conceded}",
                f"GD{self.gd}",
                f"Pts{self.points}",
            )
        )


def validate_deduction_date(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    """Validate that a value conforms to a valid DOB string.

    Allows empty string and yyyy-mm-dd.
    Any other format will raise a :exc:`ValueError`.

    :param value: DOB to validate
    :type value: :class:`typing.Any`
    :param handler: Pydantic validation handler
    :type handler: :class:`pydantic.ValidatorFunctionWrapHandler`
    :returns: Validated value in `yyyy-mm-dd` format
    :rtype: str
    :raises: :exc:`ValueError` if format is invalid
    """
    # Will raise a ValidationError for a non-string
    date = cast(str, handler(value))

    # Accept the empty string
    if date == "":
        return date

    # yyyy-mm-dd regex
    pattern = re.compile(r"[12][09]\d{2}-[01]\d-[0-3]\d$")

    # Matches - return as validated
    if re.match(pattern, date):
        return date

    raise ValueError(f"{date} is not a valid ISO date format.")


class Deduction(BaseModel):
    """A points deduction.

    :param team: Team to which this deduction applies
    :type team: str
    :param points: Number of points deducted
    :type points: int
    :param date: Date on which the deduction was implemented - if the empty string
                 the deduction should be built in from the start of the season
                 (default='')
    :type date: str
    """

    team: str
    points: PositiveInt
    date: Annotated[str, WrapValidator(validate_deduction_date)] = ""


class EventInfo(BaseModel):
    """Event data with match info added.

    :param date: Date of match
    :type date: :class:`datetime.date`
    :param teams: Teams involved in the match
    :type teams: :class:`Teams`
    :param score: Match score
    :type score: :class:`Score`
    :param event: Event info
    :type event: :class:`Event`
    """

    date: datetime.date
    teams: Teams
    score: Score
    event: Event


class League(BaseModel):
    """Represents a League.

    :param league_id: API ID of this league
    :type league_id: int
    :param name: Name of this league e.g. Premiership
    :type name: str
    :param year: Year this season starts
    :type year: int
    :param start: League start date as an ISO format string
    :type start: str
    :param end: League end date as an ISO format string
    :type end: str
    :param current: Whether this league is still being played
    :type current: bool
    :param coverage: Coverage available from the API
    :type coverage: dict[str, bool]
    :param teams: The name of each team in this league (default=[])
    :type teams: list[str]
    :param rounds: This league's rounds, with matches for each round (default={})
    :type rounds: dict[str, list[:class:`Match`]]
    :param excluded: Rounds to exclude from import (default=[])
    :type excluded: list[str]
    :param split: Split point of this league (default=0)
    :type split: int
    :param players: Players who feature in this league
    :type players: dict[int, :class:'Player']
    """

    league_id: PositiveInt
    name: str
    year: PositiveInt
    start: str = Field(pattern=r"^[12][09]\d{2}-[01]\d-[0-3]\d$")
    end: str = Field(pattern=r"^[12][09]\d{2}-[01]\d-[0-3]\d$")
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
        """Title of this league e.g. Premiership 2023/24

        :returns: Title of the league
        :rtype: str
        """
        year1 = int(self.start[:4])
        year2 = int(self.end[:4])
        season = year1 if year1 == year2 else f"{year1}/{year2 % 100}"
        return f"{self.name} {season}"

    def matches(self, team: Optional[str] = None) -> list[Match]:
        """Matches in this league.

        If ``team`` is given, return only matches
        involving this team, otherwise return all matches.

        :param team: Get matches for this team (default=None)
        :type team: str
        :returns: Matches sorted by date and then home team
        :rtype: list[:class:`Match`]
        """
        _matches = []
        for m in self.rounds.values():
            for match in m:
                if team is None or match.involves(team):
                    _matches.append(match)

        _matches.sort(key=attrgetter("teams.home"))
        _matches.sort(key=attrgetter("date"))
        return _matches

    def events(self, player: BasePlayer) -> list[EventInfo]:
        """Get all events in this league in which a player is involved.

        Also includes a :class:`LineupStatus` event for any matches
        which include the player in their lineup.

        :param player: Find events featuring this player
        :type player: :class:`BasePlayer`
        :returns: The events in this league involving the player
        :rtype: list[:class:`EventInfo`]
        """
        e = []
        for match in self.matches():
            # Find player in lineups
            status = None
            for team, lineup in zip(
                (match.teams.home, match.teams.away),
                (match.lineups.home, match.lineups.away),
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
    ):
        """Replace all occurrences of ``old`` with ``new``.

        Searches all lineups and events in this league and
        replaces all occurrences of ``old`` with ``new``.

        If `team` is given, replace only occurrences where the player
        features for `team`.

        :param old: Player to be replaced
        :type old: :class:`BasePlayer`
        :param new: New player details
        :type new: :class:`BasePlayer`
        :param team: If given, replace only where the player features for this team (default=None)
        :type team: str
        """
        for matches in self.rounds.values():
            for match in matches:
                if team is None or match.involves(team):
                    if old in match.players():
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
                                team is None
                                or (goal.goal_type == "O" and goal.team != team)
                                or (goal.goal_type != "O" and goal.team == team)
                            ):
                                if goal.scorer == old:
                                    goal.scorer = new

                        for card in match.cards:
                            if (
                                team is None or card.team == team
                            ) and card.player == old:
                                card.player = new

                        for sub in match.substitutions:
                            if team is None or sub.team == team:
                                if sub.player_on == old:
                                    sub.player_on = new
                                elif sub.player_off == old:
                                    sub.player_off = new

    def player_teams(self, player: BasePlayer) -> list[str]:
        """Get all the teams a player features in during this season.

        :param player: Find teams this player plays for
        :type player: :class:`BasePlayer`
        :returns: The teams the player plays for in this league
        :rtype: list[str]
        """
        teams = set()

        # Check each match as a player may play for more than
        # one team during a single season
        for match in self.matches():
            if player in match.players():
                found = False

                # Check lineups
                if match.lineups:
                    if player in match.lineups.home.players():
                        teams.add(match.teams.home)
                        found = True
                    elif player in match.lineups.away.players():
                        teams.add(match.teams.away)
                        found = True

                # If the player is not in the lineups
                # check all events
                if not found:
                    for event in match.events():
                        match event:
                            case Goal(scorer=scorer, goal_type=goal_type):
                                if scorer == player:
                                    # Adjust for own goal (an event for the opposing team)
                                    if goal_type == "O":
                                        teams.add(
                                            match.teams.home
                                            if event.team == match.teams.away
                                            else match.teams.away
                                        )
                                    else:
                                        teams.add(event.team)
                                    break

                            case Card(player=card_player):
                                if card_player == player:
                                    teams.add(event.team)
                                    break

                            case Substitution(
                                player_on=player_on, player_off=player_off
                            ):
                                if player in (player_on, player_off):
                                    teams.add(event.team)
                                    break

        return list(teams)

    def table(
        self,
        played: int = 0,
        split_point: bool = False,
        date: Optional[datetime.date] = None,
    ) -> list[RowTuple]:
        """Get the league table.

        Returns the league table as a list of :type:`RowTuple` items,
        ordered by league position.

        If ``played`` is non-zero the table will be returned at
        the first point at which all teams have played at least
        ``played`` matches.

        If ``split_point`` is ``True`` the table will be returned
        at the league's split point.

        If ``date`` is not ``None`` the table will be returned
        at the given date, i.e. taking account only of matches
        where the date is earlier than or equal to ``date``.

        :param played: If non-zero, get table after this number of games (default=0)
        :type played: int
        :param split_point: If True get the table at the split point (default=False)
        :type split_point: bool
        :param date: If given, get the league table on this date (default=None)
        :type date: :class:`datetime.date`
        :returns: The league table as a list of tuples
        :rtype: list[:type:`RowTuple`]
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
            elif match.score.home < match.score.away:
                home.lost += 1
                away.won += 1
            else:
                home.drawn += 1
                away.drawn += 1

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
            team_count = int(len(rows) / 2)
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

        :param teams: Teams to query
        :type teams: tuple[str, str]
        :returns: All matches between these two teams
        :rtype: list[:class:`Match`]
        """
        return [match for match in self.matches(teams[0]) if match.involves(teams[1])]

    def __str__(self) -> str:  # pragma: no cover
        return self.title
