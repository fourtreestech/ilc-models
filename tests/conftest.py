import random
import pytest

from faker import Faker
from faker.providers import BaseProvider

from ilc_models import BasePlayer, Player

fake = Faker()


class ILCProvider(BaseProvider):
    """Faker provider for ILC data models"""

    def player_id(self) -> int:
        """Returns a random player ID.

        :returns: Random player ID between 1 and 999,999
        :rtype: int
        """
        return random.randint(1, 999_999)

    def base_player(self) -> BasePlayer:
        """Returns a randomly generated BasePlayer.

        :returns: BasePlayer with random name and ID
        :rtype: :class:`ilc_models.BasePlayer`
        """
        return BasePlayer(
            player_id=fake.unique.player_id(),
            name=f"{fake.first_name()[0]}. {fake.last_name()}",
        )

    def player(self) -> Player:
        """Returns a randomly generated Player.

        :returns: Player with randomly generated attributes
        :rtype: :class:`ilc_models.Player`
        """
        player_id = fake.unique.player_id()
        first_name = fake.first_name_male()
        last_name = fake.last_name_male()
        name = f"{first_name[0]}. {last_name}"
        dob = fake.date_of_birth(minimum_age=17, maximum_age=35).isoformat()
        nationality = fake.country()

        return Player(
            player_id=player_id,
            name=name,
            first_name=first_name,
            last_name=last_name,
            dob=dob,
            nationality=nationality,
        )


fake.add_provider(ILCProvider)


@pytest.fixture(scope="session")
def ilc_fake():
    return fake
