"""User account models."""

import datetime
from typing import Annotated, Any, Literal, Optional, Self

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import AfterValidator, BaseModel, EmailStr, Field, model_validator

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


def validate_created_at(
    value: Optional[datetime.datetime],
) -> Optional[datetime.datetime]:
    """Normalise a timestamp to UTC, treating a naive timestamp as UTC.

    MongoDB stores datetimes in UTC, and pymongo returns them naive unless
    the client is created with `tz_aware=True`, so a naive value is assumed
    to already be in UTC rather than local time. `None` passes through unchanged.

    Args:
        value: Timestamp to normalise.

    Returns:
        The same instant as an offset-aware UTC timestamp, or `None`.
    """
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def validate_teams(value: list[str]) -> list[str]:
    """Clean a list of team names.

    Strips surrounding whitespace, drops names left empty, and removes duplicates
    while keeping the first occurrence's position. Case is preserved, so names
    differing only in case are kept as distinct teams.

    Args:
        value: Team names to clean.

    Returns:
        The cleaned team names.
    """
    return list(dict.fromkeys(name.strip() for name in value if name.strip()))


class UserPublic(BaseModel):
    """Represents the public view of a user, safe to return from the API.

    Attributes:
        email: The user's email address.
        username: The user's username.
        status: The user's account status, either "pending" or "active" (default="pending").
        created_at: When this user was created, as an offset-aware UTC timestamp. `None`
            if unknown, such as for a user stored before this field existed; it is never
            filled in on load, so a missing value stays missing (default=None).
        teams: The user's favourite teams, with whitespace stripped, empty names
            dropped and duplicates removed (default=[]).
    """

    email: EmailStr
    username: str
    status: Literal["pending", "active"] = "pending"
    created_at: Annotated[
        Optional[datetime.datetime], AfterValidator(validate_created_at)
    ] = None
    teams: Annotated[list[str], AfterValidator(validate_teams)] = []


class User(UserPublic):
    """Represents a user as stored in the database, including the password hash.

    A user can be built from either a plain text `password`, which is hashed on validation,
    or a `password_hash`, such as one loaded from the database, but not both.

    Attributes:
        password_hash: Argon2 hash of the user's password.
    """

    password_hash: str = Field(repr=False)

    @classmethod
    def create(
        cls,
        email: str,
        password: str,
        username: Optional[str] = None,
        status: Literal["pending", "active"] = "pending",
        teams: Optional[list[str]] = None,
    ) -> Self:
        """Create a new user from a plain text password.

        The user's `created_at` is set to the current UTC time.

        Args:
            email: The user's email address.
            password: The plain text password, which is hashed and not stored.
            username: The user's username. If not provided the first part of the
                e-mail address (before the '@') will be used.
            status: The user's status (default="pending").
            teams: The user's favourite teams (default=[]).

        Returns:
            The new user.

        Raises:
            ValidationError: If the email is invalid or the password is not a non-empty string.
        """
        name = username or email.split("@")[0]
        return cls.model_validate(
            {
                "email": email,
                "password": password,
                "username": name,
                "status": status,
                "teams": teams or [],
                "created_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )

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
