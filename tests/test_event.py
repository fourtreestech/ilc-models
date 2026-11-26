"""Tests for event models"""

import pytest

from ilc_models import (
    Card,
    EventTime,
    Goal,
    Substitution,
)


class TestEvents:
    def test_event_time_raises_error(self):
        with pytest.raises(ValueError):
            EventTime(minutes=60, plus=5)

    def test_event_time_str_without_plus_time(self, ilc_fake):
        t = EventTime(minutes=37)
        assert str(t) == "37'"

    def test_event_time_str_with_plus_time(self, ilc_fake):
        t = EventTime(minutes=90, plus=3)
        assert str(t) == "90+3'"

    def test_goal_returns_player(self, ilc_fake):
        player = ilc_fake.base_player()
        goal = Goal(
            team=ilc_fake.team_name(), time=ilc_fake.event_time(), scorer=player
        )
        assert goal.players() == [player]

    def test_card_returns_player(self, ilc_fake):
        player = ilc_fake.base_player()
        card = Card(
            team=ilc_fake.team_name(),
            time=ilc_fake.event_time(),
            player=player,
            color="Y",
        )
        assert card.players() == [player]

    def test_sub_returns_players(self, ilc_fake):
        player_on = ilc_fake.base_player()
        player_off = ilc_fake.base_player()
        sub = Substitution(
            team=ilc_fake.team_name(),
            time=ilc_fake.event_time(),
            player_on=player_on,
            player_off=player_off,
        )
        assert all(p in sub.players() for p in (player_on, player_off))

    def test_event_str_without_plus_time(self, ilc_fake):
        event = Goal(
            team=ilc_fake.team_name(),
            time=EventTime(minutes=37),
            scorer=ilc_fake.player(),
        )
        assert event.time_str() == "37'"

    def test_event_str_with_plus_time(self, ilc_fake):
        event = Goal(
            team=ilc_fake.team_name(),
            time=EventTime(minutes=90, plus=3),
            scorer=ilc_fake.player(),
        )
        assert event.time_str() == "90+3'"

    def test_event_str_returns_players(self, ilc_fake):
        player = ilc_fake.player()
        event = Goal(
            team=ilc_fake.team_name(), time=EventTime(minutes=37), scorer=player
        )
        assert event.players() == [player]
