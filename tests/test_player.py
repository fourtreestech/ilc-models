"""Tests for player models"""

import pytest
from pydantic import ValidationError

from ilc_models import (
    BasePlayer,
    Player,
)


class TestBasePlayer:
    def test_base_player_str_returns_name(self, ilc_fake):
        player = ilc_fake.base_player()
        assert str(player) == player.name

    def test_equality_ignores_name_if_id_is_non_zero(self, ilc_fake):
        player1 = ilc_fake.base_player()

        # Shorten name by one letter
        player2 = BasePlayer(player_id=player1.player_id, name=player1.name[:-1])

        # Should be equal because ID numbers are equal
        assert player1 == player2
        assert player1 in [player2]

    def test_equality_compares_name_if_id_is_zero(self, ilc_fake):
        player1 = ilc_fake.base_player()
        player1.player_id = 0

        # Shorten name by one letter
        player2 = BasePlayer(player_id=player1.player_id, name=player1.name[:-1])

        # Should be unequal because ID numbers are zero and names don't match
        assert player1 != player2
        assert player1 not in [player2]

    def test_equality_compares_true_if_id_is_zero_and_names_match(self, ilc_fake):
        player1 = ilc_fake.base_player()
        player1.player_id = 0

        # Make identical player
        player2 = BasePlayer(player_id=player1.player_id, name=player1.name)

        # Should be equal because ID numbers are zero and names match
        assert player1 == player2
        assert player1 in [player2]


class TestPlayer:
    def test_player_str_returns_name(self, ilc_fake):
        player = ilc_fake.player()
        assert str(player) == player.name

    def test_dob_rejects_pre_1900(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()
        player_dict["dob"] = "1899-31-12"
        with pytest.raises(ValidationError):
            Player(**player_dict)

    def test_dob_rejects_date_time_format(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()
        player_dict["dob"] = "2025-03-25T20:49:21"
        with pytest.raises(ValidationError):
            Player(**player_dict)

    def test_dob_accepts_empty_string(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()

        # Set to empty string
        player_dict["dob"] = ""
        assert Player(**player_dict).dob == ""

    def test_dob_accepts_missing_zeros(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()

        # Set to empty string
        player_dict["dob"] = "2000-9-7"
        assert Player(**player_dict).dob == "2000-09-07"

    def test_dob_rejects_impossible_month_and_day(self, ilc_fake):
        player_dict = ilc_fake.player().model_dump()
        player_dict["dob"] = "2020-19-39"
        with pytest.raises(ValidationError):
            Player(**player_dict)

    def test_dob_rejects_impossible_calendar_date(self, ilc_fake):
        player_dict = ilc_fake.player().model_dump()
        player_dict["dob"] = "2021-02-29"
        with pytest.raises(ValidationError):
            Player(**player_dict)
