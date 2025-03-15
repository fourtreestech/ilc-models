import random
import pytest

from faker import Faker
from faker.providers import BaseProvider

from ilc_models import BasePlayer, Lineup, Lineups, Player

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

    def lineup(self) -> Lineup:
        """Returns a randomly generated Lineup.

        Creates a lineup with 7 substitutes.

        :returns: Lineup with randomly generated players
        :rtype: :class:`ilc_models.Lineup`
        """
        # Prefer 2-11, then 12-19 then 20-39
        shirts = list(range(2, 40))
        shirt_weights = [3] * 10 + [2] * 8 + [1] * 20

        # Generate random shirt numbers for this lineup
        shirt_numbers: list[int] = []
        while len(shirt_numbers) < 17:
            n = random.choices(shirts, weights=shirt_weights)[0]
            shirt_numbers.append(n)
            i = shirts.index(n)
            del shirts[i]
            del shirt_weights[i]

        # Select one for the second goalkeeper
        keeper2 = random.choice([n for n in shirt_numbers if n > 11])
        shirt_numbers.remove(keeper2)

        # Decide which goalkeeper will start
        keepers = [1, keeper2]
        random.shuffle(keepers)

        # Get starting XI
        starting_shirts = [keepers[0]] + shirt_numbers[:10]
        starting = [(shirt, self.base_player()) for shirt in starting_shirts]

        # Get subs
        sub_shirts = [keepers[1]] + shirt_numbers[10:]
        subs = [(shift, self.base_player()) for shift in sub_shirts]

        return Lineup(starting=starting, subs=subs)

    def lineups(self) -> Lineups:
        """Returns two randomly generated lineups.

        :returns: Lineups with randomly generated players
        :rtype: :class:`ilc_models.Lineups`
        """
        return Lineups(home=self.lineup(), away=self.lineup())


fake.add_provider(ILCProvider)


@pytest.fixture(scope="session")
def ilc_fake():
    return fake
