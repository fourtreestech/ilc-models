"""Tests for user models"""

import datetime

import pytest
from argon2 import PasswordHasher
from pydantic import ValidationError

from ilc_models import (
    User,
    UserPublic,
)


class TestUser:
    def test_verifies_password(self):
        user = User.create(email="user@user.com", password="abcde")
        assert user.verify_password("abcde")

    def test_fails_password_check(self):
        user = User.create(email="user@user.com", password="abcde")
        assert not user.verify_password("12345")

    def test_verify_returns_false_for_malformed_hash(self):
        user = User(email="user@user.com", password_hash="not-a-hash", username="user")
        assert not user.verify_password("abcde")

    def test_verify_returns_false_for_empty_hash(self):
        user = User(email="user@user.com", password_hash="", username="user")
        assert not user.verify_password("abcde")

    @pytest.mark.parametrize("password", [None, 123, b"abcde", ""])
    def test_invalid_password_raises_validation_error(self, password):
        with pytest.raises(ValidationError, match="non-empty string"):
            User.model_validate({"email": "user@user.com", "password": password})

    def test_create_rejects_empty_password(self):
        with pytest.raises(ValidationError):
            User.create(email="user@user.com", password="")

    def test_create_defaults_username_to_email_local_part(self):
        user = User.create(email="someone@user.com", password="abcde")
        assert user.username == "someone"

    def test_create_uses_given_username(self):
        user = User.create(email="someone@user.com", password="abcde", username="bob")
        assert user.username == "bob"

    @pytest.mark.parametrize("username", [None, ""])
    def test_create_falls_back_to_email_when_username_blank(self, username):
        user = User.create(
            email="someone@user.com", password="abcde", username=username
        )
        assert user.username == "someone"

    def test_create_defaults_status_to_pending(self):
        user = User.create(email="user@user.com", password="abcde")
        assert user.status == "pending"

    def test_create_uses_given_status(self):
        user = User.create(email="user@user.com", password="abcde", status="active")
        assert user.status == "active"

    def test_create_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            User.create(email="user@user.com", password="abcde", status="banned")  # ty: ignore[invalid-argument-type]

    def test_password_and_hash_together_raises(self):
        stored = User.create(email="user@user.com", password="abcde")
        with pytest.raises(ValidationError, match="not both"):
            User.model_validate(
                {
                    "email": "user@user.com",
                    "password_hash": stored.password_hash,
                    "password": "",
                }
            )

    def test_validator_hashes_password_without_mutating_input(self):
        data = {"email": "user@user.com", "password": "abcde", "username": "user"}
        user = User.model_validate(data)
        assert user.verify_password("abcde")
        assert data == {
            "email": "user@user.com",
            "password": "abcde",
            "username": "user",
        }

    def test_verify_does_not_modify_outdated_hash(self):
        old_hash = PasswordHasher(time_cost=1).hash("abcde")
        user = User(email="user@user.com", password_hash=old_hash, username="user")
        assert user.verify_password("abcde")
        assert user.password_hash == old_hash

    def test_needs_rehash_for_outdated_hash_until_password_is_set(self):
        old_hash = PasswordHasher(time_cost=1).hash("abcde")
        user = User(email="user@user.com", password_hash=old_hash, username="user")
        assert user.needs_rehash()

        user.set_password("fghij")
        assert not user.needs_rehash()
        assert user.verify_password("fghij")
        assert not user.verify_password("abcde")

    def test_new_user_does_not_need_rehash(self):
        user = User.create(email="user@user.com", password="abcde")
        assert not user.needs_rehash()

    @pytest.mark.parametrize("password_hash", ["", "not-a-hash"])
    def test_malformed_hash_needs_rehash(self, password_hash):
        user = User(email="user@user.com", password_hash=password_hash, username="user")
        assert user.needs_rehash()

    @pytest.mark.parametrize("password", [None, 123, ""])
    def test_set_password_rejects_invalid_password(self, password):
        user = User.create(email="user@user.com", password="abcde")
        old_hash = user.password_hash
        with pytest.raises(ValueError, match="non-empty string"):
            user.set_password(password)
        assert user.password_hash == old_hash

    @pytest.mark.parametrize("email", ["not-an-email", "", "user@"])
    def test_invalid_email_raises_validation_error(self, email):
        with pytest.raises(ValidationError):
            User.create(email=email, password="abcde")
        with pytest.raises(ValidationError):
            UserPublic(email=email, username="user")

    def test_repr_hides_password_hash(self):
        user = User.create(email="user@user.com", password="abcde")
        assert "password_hash" not in repr(user)
        assert user.password_hash not in repr(user)

    def test_dump_includes_password_hash(self):
        user = User.create(email="user@user.com", password="abcde")
        assert user.model_dump()["password_hash"] == user.password_hash

    def test_public_user_omits_password_hash(self):
        user = User.create(email="user@user.com", password="abcde")
        public = UserPublic.model_validate(user.model_dump())
        assert public.email == user.email
        assert "password_hash" not in public.model_dump()
        assert not hasattr(public, "password_hash")


class TestUserCreatedAt:
    def test_create_sets_created_at_to_now_utc(self):
        before = datetime.datetime.now(datetime.timezone.utc)
        user = User.create(email="user@user.com", password="abcde")
        after = datetime.datetime.now(datetime.timezone.utc)
        assert user.created_at is not None
        assert user.created_at.utcoffset() == datetime.timedelta(0)
        assert before <= user.created_at <= after

    def test_missing_created_at_stays_none_on_load(self):
        # A user stored before created_at existed must not get a made-up value.
        doc = {"email": "user@user.com", "username": "user", "password_hash": "x"}
        assert User.model_validate(doc).created_at is None
        assert UserPublic(email="user@user.com", username="user").created_at is None

    def test_missing_created_at_round_trips_as_none(self):
        doc = {"email": "user@user.com", "username": "user", "password_hash": "x"}
        user = User.model_validate(doc)
        assert User.model_validate(user.model_dump()).created_at is None

    def test_naive_created_at_is_treated_as_utc(self):
        # pymongo returns naive UTC datetimes unless tz_aware=True.
        naive = datetime.datetime(2025, 8, 1, 12, 30)
        user = UserPublic(email="user@user.com", username="user", created_at=naive)
        assert user.created_at == datetime.datetime(
            2025, 8, 1, 12, 30, tzinfo=datetime.timezone.utc
        )

    def test_aware_created_at_is_normalised_to_utc(self):
        bst = datetime.timezone(datetime.timedelta(hours=1))
        aware = datetime.datetime(2025, 8, 1, 13, 30, tzinfo=bst)
        user = UserPublic(email="user@user.com", username="user", created_at=aware)
        assert user.created_at is not None
        assert user.created_at.tzinfo == datetime.timezone.utc
        assert user.created_at == datetime.datetime(
            2025, 8, 1, 12, 30, tzinfo=datetime.timezone.utc
        )

    def test_iso_string_created_at_is_parsed(self):
        user = UserPublic(
            email="user@user.com", username="user", created_at="2025-08-01T12:30:00Z"
        )
        assert user.created_at == datetime.datetime(
            2025, 8, 1, 12, 30, tzinfo=datetime.timezone.utc
        )

    def test_loaded_and_new_users_are_comparable(self):
        new = User.create(email="new@user.com", password="abcde")
        stored = new.model_dump()
        stored["created_at"] = stored["created_at"].replace(tzinfo=None)
        loaded = User.model_validate(stored)
        assert loaded.created_at == new.created_at
        assert loaded.created_at is not None and new.created_at is not None
        assert loaded.created_at <= datetime.datetime.now(datetime.timezone.utc)

    def test_created_at_round_trips_through_dump(self):
        user = User.create(email="user@user.com", password="abcde")
        assert User.model_validate(user.model_dump()).created_at == user.created_at
        assert (
            User.model_validate_json(user.model_dump_json()).created_at
            == user.created_at
        )

    def test_invalid_created_at_raises(self):
        with pytest.raises(ValidationError):
            UserPublic(email="user@user.com", username="user", created_at="not-a-date")


class TestUserTeams:
    def test_teams_default_to_empty_list(self):
        user = User.create(email="user@user.com", password="abcde")
        assert user.teams == []

    def test_teams_default_is_not_shared(self):
        first = UserPublic(email="a@user.com", username="a")
        second = UserPublic(email="b@user.com", username="b")
        first.teams.append("Celtic")
        assert second.teams == []

    def test_teams_round_trip_through_dump(self):
        user = User.create(email="user@user.com", password="abcde")
        user.teams = ["Celtic", "Hibernian"]
        assert User.model_validate(user.model_dump()).teams == ["Celtic", "Hibernian"]

    def test_teams_are_cleaned(self):
        user = UserPublic(
            email="user@user.com",
            username="user",
            teams=[" Celtic ", "", "  ", "Hibernian", "Celtic", "celtic"],
        )
        assert user.teams == ["Celtic", "Hibernian", "celtic"]

    def test_create_uses_given_teams(self):
        user = User.create(
            email="user@user.com", password="abcde", teams=["Celtic", "Celtic"]
        )
        assert user.teams == ["Celtic"]
