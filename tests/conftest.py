import random
import pytest

from faker import Faker
from faker.providers import BaseProvider

from ilc_models import BasePlayer

fake = Faker()


class ILCProvider(BaseProvider):
    def player_id(self):
        return random.randint(1, 999_999)

    def base_player(self):
        return BasePlayer(
            player_id=fake.unique.player_id(),
            name=f"{fake.first_name()[0]}. {fake.last_name()}",
        )


fake.add_provider(ILCProvider)


@pytest.fixture(scope="session")
def ilc_fake():
    return fake
