"""Tests for data models"""

from ilc_models import BasePlayer

class TestBasePlayer:

    def test_base_player_str_returns_name(self):
        player = BasePlayer(player_id=123456, name="L. Messi")
        assert str(player) == "L. Messi"