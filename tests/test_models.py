"""Tests for data models"""

from ilc_models import Lineup, Lineups


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
