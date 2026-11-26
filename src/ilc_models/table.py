"""League table and points deduction models."""

import datetime
import functools
import re
from typing import Annotated, Any, Literal, NamedTuple, cast

from pydantic import (
    BaseModel,
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)


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


# yyyy-mm-dd, zero-padding required
_DATE_PATTERN = re.compile(r"[12][09]\d{2}-[01]\d-[0-3]\d$")


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
