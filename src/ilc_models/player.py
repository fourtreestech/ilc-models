"""Player models."""

import datetime
import re
from typing import Annotated, Any, cast

from pydantic import BaseModel, ValidatorFunctionWrapHandler, WrapValidator


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
