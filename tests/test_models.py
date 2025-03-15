"""Tests for data models"""

from ilc_models import Card, Goal, Lineup, Lineups, Substitution


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
