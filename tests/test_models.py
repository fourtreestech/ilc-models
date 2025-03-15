"""Tests for data models"""

import datetime

from ilc_models import Card, Event, Goal, Lineup, Lineups, Substitution


class TestBasePlayer:
    def test_base_player_str_returns_name(self, ilc_fake):
        player = ilc_fake.base_player()
        assert str(player) == player.name


class TestPlayer:
    def test_player_str_returns_name(self, ilc_fake):
        player = ilc_fake.player()
        assert str(player) == player.name


class TestLineup:
    def test_empty_lineup_is_falsy(self):
        assert not Lineup()

    def test_populated_lineup_is_truthy(self, ilc_fake):
        lineup = ilc_fake.lineup()
        assert lineup

    def test_sort_leaves_starting_goalkeeper_first(self, ilc_fake):
        lineup = ilc_fake.lineup()
        starting_keeper = lineup.starting[0][0]
        lineup.sort()
        assert lineup.starting[0][0] == starting_keeper

    def test_sort_order(self, ilc_fake):
        lineup = ilc_fake.lineup()
        lineup.sort()
        starting = [p[0] for p in lineup.starting[1:]]
        subs = [p[0] for p in lineup.subs]
        assert starting == sorted(starting)
        assert subs == sorted(subs)

    def test_players(self, ilc_fake):
        lineup = ilc_fake.lineup()
        players = lineup.players()
        assert len(players) == 18

    def test_shirt_numbers_are_unique(self, ilc_fake):
        lineup = ilc_fake.lineup()
        shirt_numbers = [p[0] for p in lineup.starting] + [p[0] for p in lineup.subs]
        assert len(shirt_numbers) == len((set(shirt_numbers)))


class TestLineups:
    def test_empty_lineups_is_falsy(self):
        assert not Lineups()

    def test_populated_lineups_is_truthy(self, ilc_fake):
        lineups = ilc_fake.lineups()
        assert lineups

    def test_sort_order(self, ilc_fake):
        lineups = ilc_fake.lineups()
        lineups.sort()
        starting = [p[0] for p in lineups.home.starting[1:]]
        subs = [p[0] for p in lineups.home.subs]
        assert starting == sorted(starting)
        assert subs == sorted(subs)
        starting = [p[0] for p in lineups.away.starting[1:]]
        subs = [p[0] for p in lineups.away.subs]
        assert starting == sorted(starting)
        assert subs == sorted(subs)


class TestEvents:
    def test_goal_returns_player(self, ilc_fake):
        player = ilc_fake.base_player()
        goal = Goal(scorer=player)
        assert goal.players() == [player]

    def test_card_returns_player(self, ilc_fake):
        player = ilc_fake.base_player()
        card = Card(player=player, color="Y")
        assert card.players() == [player]

    def test_sub_returns_players(self, ilc_fake):
        player_on = ilc_fake.base_player()
        player_off = ilc_fake.base_player()
        sub = Substitution(player_on=player_on, player_off=player_off)
        assert all(p in sub.players() for p in (player_on, player_off))

    def test_event_str_without_plus_time(self, ilc_fake):
        event = Event(
            team=ilc_fake.team_name(), time=37, detail=Goal(scorer=ilc_fake.player())
        )
        assert event.time_str() == "37'"

    def test_event_str_with_plus_time(self, ilc_fake):
        event = Event(
            team=ilc_fake.team_name(),
            time=90,
            plus=3,
            detail=Goal(scorer=ilc_fake.player()),
        )
        assert event.time_str() == "90+3'"

    def test_event_str_returns_players(self, ilc_fake):
        player = ilc_fake.player()
        event = Event(team=ilc_fake.team_name(), time=37, detail=Goal(scorer=player))
        assert event.players() == [player]


class TestMatch:
    def test_match_returns_played_true(self, ilc_fake):
        match = ilc_fake.match()
        assert match.played

    def test_match_date(self, ilc_fake):
        kickoff = datetime.datetime(
            2025, 2, 1, 15, tzinfo=datetime.timezone(datetime.timedelta())
        )
        match = ilc_fake.match(kickoff=kickoff)
        assert match.date == datetime.date(2025, 2, 1)

    def test_involves(self, ilc_fake):
        home = ilc_fake.team()
        away = ilc_fake.team()
        other = ilc_fake.team()
        match = ilc_fake.match(home=home, away=away)
        assert match.involves(home.name)
        assert match.involves(away.name)
        assert not match.involves(other.name)
