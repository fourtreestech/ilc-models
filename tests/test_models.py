"""Tests for data models"""

class TestBasePlayer:

    def test_base_player_str_returns_name(self, fake_base_player):
        player = fake_base_player
        assert str(player) == player.name
