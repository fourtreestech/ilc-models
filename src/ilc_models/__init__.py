"""Data models for the ILC project.

Pure Pydantic models with no I/O, forming the shared data contract between
ilc-api, ilc-app and ilc-admin.
"""

import abc
import datetime
import functools
import math
import re
from operator import attrgetter, itemgetter
from typing import Annotated, Any, Literal, NamedTuple, Optional, Self, cast

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    model_validator,
)

__version__ = "0.3.0"

_ph = PasswordHasher()


def _hash_password(password: Any) -> str:
    """Hash a plain text password.

    Args:
        password: The plain text password.

    Returns:
        The argon2 hash of the password.

    Raises:
        ValueError: If the password is not a non-empty string.
    """
    if not isinstance(password, str) or not password:
        msg = "password must be a non-empty string"
        raise ValueError(msg)
    return _ph.hash(password)


class RowTuple(NamedTuple):
    """A single row of a league table, as a plain tuple.

    Fields, in order: `team`, `played`, `won`, `drawn`, `lost`, `goals_for`,
    `goals_against`, `gd`, `points`, `form`.
    """

    team: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    gd: int
    points: int
    form: str


class BasePlayer(BaseModel):
    """Basic level of player details.

    Attributes:
        player_id: ID of this player in the API.
        name: Player's full (display) name.
    """

    player_id: int
    name: str

    def __str__(self) -> str:
        """Return the player's name.

        Returns:
            The player's `name`.
        """
        return self.name

    def __eq__(self, other) -> bool:
        """Return True if `self` and `other` are equal.

        If `player_id` is non-zero the equality comparison will return `True`
        if player IDs match i.e. ignores different values of `name`.
        This is because there are often slight variances in the API between player names
        in events and in downloaded player data, which would otherwise cause mismatches
        when finding players in events.

        If `player_id` is zero in both `self` and `other` then the player names
        will also be compared.

        Args:
            other: Player to compare to.

        Returns:
            `True` if the players are equal.
        """
        try:
            if self.player_id == 0 and other.player_id == 0:
                return self.name == other.name
            return self.player_id == other.player_id

        except AttributeError:  # pragma: no cover
            return NotImplemented


# yyyy-mm-dd, with zero-padding optional
_DOB_PATTERN = re.compile(r"([12][09]\d{2})-(\d{1,2})-(\d{1,2})$")

# yyyy-mm-dd, zero-padding required
_DATE_PATTERN = re.compile(r"[12][09]\d{2}-[01]\d-[0-3]\d$")


def validate_dob(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    """Validate that a value conforms to a valid DOB string.

    Allows empty string, yyyy-m-d and yyyy-mm-dd, provided the year, month and
    day form a real calendar date.
    Any other format, or an impossible date such as month 19 or 29 February
    in a non-leap year, will raise a `ValueError`.

    Args:
        value: DOB to validate.
        handler: Pydantic validation handler.

    Returns:
        Validated value in `yyyy-mm-dd` format, or the empty string unchanged.

    Raises:
        ValueError: If the format is invalid or the date is not a real calendar date.
    """
    # Will raise a ValidationError for a non-string
    dob = cast(str, handler(value))

    # Accept the empty string
    if dob == "":
        return dob

    match = _DOB_PATTERN.match(dob)
    if not match:
        raise ValueError(f"{dob} is not a valid ISO date format.")

    # Confirm it's a real calendar date, and normalise to yyyy-mm-dd
    year, month, day = (int(n) for n in match.groups())
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError as exc:
        raise ValueError(f"{dob} is not a valid ISO date.") from exc


class Player(BasePlayer):
    """Full player details.

    Attributes:
        first_name: Player's first name.
        last_name: Player's last name.
        dob: Player's date of birth in ISO (yyyy-mm-dd) format, or the empty
            string if unknown.
        nationality: Player's nationality.
    """

    first_name: str
    last_name: str
    dob: Annotated[str, WrapValidator(validate_dob)]
    nationality: str

    @property
    def base_player(self) -> BasePlayer:
        """Return a `BasePlayer` object corresponding to this `Player`.

        Returns:
            A `BasePlayer` with this player's `player_id` and `name`, dropping
            the other fields.
        """
        return BasePlayer(player_id=self.player_id, name=self.name)


class Lineup(BaseModel):
    """Lineup for one team.

    Each lineup entry is an (int, BasePlayer) tuple, with the int
    being the player's shirt number if supplied (0 if not).

    Attributes:
        starting: Starting XI, at most 11 players (default=[]).
        subs: Substitutes (default=[]).
    """

    starting: list[tuple[int, BasePlayer]] = Field(max_length=11, default=[])
    subs: list[tuple[int, BasePlayer]] = []

    def __bool__(self) -> bool:
        """Return True if this lineup is populated with players.

        Returns:
            `True` if this lineup contains at least one player.
        """
        return len(self.starting) + len(self.subs) > 0

    def sort(self) -> None:
        """Sort the lineup.

        Each part of the lineup is sorted by shirt number, except
        for the first item in the starting lineup which is
        assumed to be the goalkeeper and is left as the first item.
        """
        self.starting = self.starting[:1] + sorted(self.starting[1:], key=itemgetter(0))
        self.subs.sort(key=itemgetter(0))

    def players(self) -> list[BasePlayer]:
        """Return all players in this lineup.

        Returns:
            Every player in the starting XI and on the bench.
        """
        return [p[1] for p in self.starting] + [p[1] for p in self.subs]

    def __len__(self) -> int:
        """Return the total number of players in this lineup.

        Returns:
            The total number of players in this lineup.
        """
        return len(self.starting) + len(self.subs)


class Lineups(BaseModel):
    """Match lineups for home and away teams.

    Attributes:
        home: Home lineup (default=`Lineup()`).
        away: Away lineup (default=`Lineup()`).
    """

    home: Lineup = Lineup()
    away: Lineup = Lineup()

    def __bool__(self) -> bool:
        """Return True if either lineup is populated with players.

        Returns:
            `True` if the home or away lineup contains at least one player.
        """
        return bool(self.home) or bool(self.away)

    def sort(self) -> None:
        """Sort the lineups.

        Each part of the lineup is sorted by shirt number, except
        for the first item in the starting lineup which is
        assumed to be the goalkeeper and is left as the first item.
        """
        self.home.sort()
        self.away.sort()

    def players(self) -> list[BasePlayer]:
        """Return all players in these lineups.

        Returns:
            Every player in the home and away lineups.
        """
        return self.home.players() + self.away.players()

    def __len__(self) -> int:
        """Return the total number of players in these lineups.

        Returns:
            The total number of players in these lineups.
        """
        return len(self.home) + len(self.away)


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


@functools.total_ordering
class TableRow(BaseModel):
    """A row in a league table.

    Attributes:
        team: Team name.
        won: Matches won (default=0).
        drawn: Matches drawn (default=0).
        lost: Matches lost (default=0).
        scored: Goals scored (default=0).
        conceded: Goals conceded (default=0).
        deducted: Points deducted (default=0).
        form: Team form, oldest result first and at most five results,
            e.g. 'WDWWL' (default='').
    """

    team: str
    won: NonNegativeInt = 0
    drawn: NonNegativeInt = 0
    lost: NonNegativeInt = 0
    scored: NonNegativeInt = 0
    conceded: NonNegativeInt = 0
    deducted: NonNegativeInt = 0
    form: str = Field(pattern=r"^[WLD]{0,5}$", default="")

    @property
    def played(self) -> int:
        """Matches played.

        Returns:
            The total number of matches played.
        """
        return self.won + self.drawn + self.lost

    @property
    def gd(self) -> int:
        """Goal difference.

        Returns:
            The goal difference, i.e. goals scored minus goals conceded.
        """
        return self.scored - self.conceded

    @property
    def points(self) -> int:
        """Total points gained.

        Returns:
            Three points per win plus one per draw, less any `deducted` points.
        """
        return self.won * 3 + self.drawn - self.deducted

    def add_form(self, result: Literal["W", "D", "L"]) -> None:
        """Add a match result to the form field.

        Appends 'W', 'D' or 'L' to the team form, removing
        the oldest form indicator if the form is already
        displaying five matches, e.g. adding 'D' to 'WWLL'
        will result in 'WWLLD', while adding 'D' to 'WWLLD'
        will result in 'WLLDD'.

        Args:
            result: Result to add ('W', 'L' or 'D').
        """
        if len(self.form) == 5:
            self.form = f"{self.form[1:]}{result}"
        else:
            self.form = f"{self.form}{result}"

    def as_tuple(self) -> RowTuple:
        """Return this row as a `RowTuple`.

        Returns:
            This row as a `RowTuple`.
        """
        return RowTuple(
            self.team,
            self.played,
            self.won,
            self.drawn,
            self.lost,
            self.scored,
            self.conceded,
            self.gd,
            self.points,
            self.form,
        )

    @classmethod
    def from_tuple(cls, row_tuple: RowTuple) -> "TableRow":
        """Create a `TableRow` instance from a `RowTuple`.

        `RowTuple` has no `deducted` field of its own, so it is reconstructed
        from `points`, i.e. `deducted = won * 3 + drawn - points`.

        Args:
            row_tuple: Source tuple.

        Returns:
            Newly created `TableRow`.

        Raises:
            ValueError: If `row_tuple.points` is greater than `won * 3 + drawn`,
                which implies a negative deduction and cannot come from `as_tuple()`.
        """
        return cls(
            team=row_tuple.team,
            won=row_tuple.won,
            drawn=row_tuple.drawn,
            lost=row_tuple.lost,
            scored=row_tuple.goals_for,
            conceded=row_tuple.goals_against,
            deducted=row_tuple.won * 3 + row_tuple.drawn - row_tuple.points,
            form=row_tuple.form,
        )

    def __eq__(self, other: Any) -> bool:
        """Return True if `self` and `other` are equal.

        Rows are equal if their points, goal difference, goals scored and
        team name all match; other fields such as `form` are ignored.

        Args:
            other: Row to compare to.

        Returns:
            `True` if the rows are equal.
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
        """Return True if `self` is greater than `other`.

        Ordering is by points, GD and goals scored.
        If all are equal, team name will be compared
        in reverse alphabetical order so that a sorted league table
        will be ordered alphabetically.

        Args:
            other: Row to compare to.

        Returns:
            `True` if `self` is greater than `other`.
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
        """Return the row as a string, e.g. 'Team A P10 W6 D2 L2 F20 A10 GD10 Pts20 WWDLW'.

        Returns:
            The row as a string.
        """
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
                self.form,
            )
        )


def validate_deduction_date(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    """Validate that a value conforms to a valid deduction date string.

    Allows the empty string and zero-padded `yyyy-mm-dd`, provided the year,
    month and day form a real calendar date. Any other format, or an
    impossible date such as month 19 or 29 February in a non-leap year, will
    raise a `ValueError`.

    Args:
        value: Deduction date to validate.
        handler: Pydantic validation handler.

    Returns:
        Validated value, unchanged (including the empty string).

    Raises:
        ValueError: If the format is invalid or the date is not a real calendar date.
    """
    # Will raise a ValidationError for a non-string
    date = cast(str, handler(value))

    # Accept the empty string
    if date == "":
        return date

    if not _DATE_PATTERN.match(date):
        raise ValueError(f"{date} is not a valid ISO date format.")

    # Confirm it's a real calendar date
    try:
        datetime.date.fromisoformat(date)
    except ValueError as exc:
        raise ValueError(f"{date} is not a valid ISO date.") from exc

    return date


class Deduction(BaseModel):
    """A points deduction.

    Attributes:
        team: Team to which this deduction applies.
        points: Number of points deducted.
        date: Date on which the deduction took effect, as `yyyy-mm-dd`. If the
            empty string the deduction is applied from the start of the season
            (default='').
    """

    team: str
    points: PositiveInt
    date: Annotated[str, WrapValidator(validate_deduction_date)] = ""


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


class UserPublic(BaseModel):
    """Represents the public view of a user, safe to return from the API.

    Attributes:
        email: The user's email address.
    """

    email: EmailStr


class User(UserPublic):
    """Represents a user as stored in the database, including the password hash.

    A user can be built from either a plain text `password`, which is hashed on validation,
    or a `password_hash`, such as one loaded from the database, but not both.

    Attributes:
        password_hash: Argon2 hash of the user's password.
    """

    password_hash: str = Field(repr=False)

    @classmethod
    def create(cls, email: str, password: str) -> Self:
        """Create a new user from a plain text password.

        Args:
            email: The user's email address.
            password: The plain text password, which is hashed and not stored.

        Returns:
            The new user.

        Raises:
            ValidationError: If the email is invalid or the password is not a non-empty string.
        """
        return cls.model_validate({"email": email, "password": password})

    @model_validator(mode="before")
    @classmethod
    def hash_password(cls, data: Any) -> Any:
        """Convert a plain text password to a secure hash.

        Args:
            data: The raw input; a `dict` containing `password` has it replaced by `password_hash`.

        Returns:
            The input, with any plain text password replaced by its hash.

        Raises:
            ValueError: If `password` is not a non-empty string, or if both `password` and
                `password_hash` are supplied.
        """
        if isinstance(data, dict) and "password" in data:
            if "password_hash" in data:
                msg = "provide either password or password_hash, not both"
                raise ValueError(msg)
            data = dict(data)  # don't mutate the caller's dict
            data["password_hash"] = _hash_password(data.pop("password"))
        return data

    def verify_password(self, attempt: str) -> bool:
        """Verify a password attempt against the stored hash.

        This never modifies the user. After a successful check, call `needs_rehash` and
        `set_password` to upgrade an outdated hash.

        Args:
            attempt: The plain text password to check.

        Returns:
            `True` if the attempt matches; `False` if it doesn't, or if the stored hash is
            malformed or otherwise unverifiable.
        """
        try:
            _ph.verify(self.password_hash, attempt)
        except (VerificationError, InvalidHashError):
            return False
        return True

    def needs_rehash(self) -> bool:
        """Check whether the stored hash should be replaced.

        Returns:
            `True` if the hash was made with outdated parameters or is malformed.
        """
        try:
            return _ph.check_needs_rehash(self.password_hash)
        except InvalidHashError:
            return True

    def set_password(self, password: str) -> None:
        """Replace the stored hash with a hash of a new password.

        The caller is responsible for persisting the user afterwards.

        Args:
            password: The new plain text password.

        Raises:
            ValueError: If the password is not a non-empty string.
        """
        self.password_hash = _hash_password(password)
