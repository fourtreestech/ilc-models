import random
import pytest

from ilc_models import BasePlayer

@pytest.fixture
def fake_base_player(faker):
    return BasePlayer(
        player_id=random.randint(1, 999_999),
        name=f"{faker.first_name()[0]}. {faker.last_name()}"
    )
