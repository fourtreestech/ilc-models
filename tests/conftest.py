import random
import pytest
from collections.abc import MutableSequence
from typing import Optional, Any

from faker import Faker
from faker.providers import BaseProvider

from ilc_models import BasePlayer, Lineup, Lineups, Player

fake = Faker()


class SquadPlayer:
    """Member of a squad.

    On initialization the object will be populated
    with a randomly generated :class:`~ilc_models.BasePlayer`
    and will be allocated two weighting attributes:

        * ``selection_weight``: How likely this player is to be selected (1-100)
        * ``scorer_weight``: How likely this player is to score a goal (1-100)

    :param shirt_number: Player's squad number
    :type shirt_number: int
    :param keeper: True if this player is a goalkeeper (default=False)
    :type keeper: bool
    """

    def __init__(self, shirt_number: int, keeper=False):
        self.shirt_number = shirt_number
        self.keeper = keeper
        self.base_player = fake.base_player()
        self.selection_weight = random.randint(1, 100)
        self.scorer_weight = 1 if keeper else random.randint(2, 100)


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
        shirt_numbers = _unique_choices(shirts, weights=shirt_weights, k=17)

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
        subs = [(shirt, self.base_player()) for shirt in sub_shirts]

        return Lineup(starting=starting, subs=subs)

    def lineups(self) -> Lineups:
        """Returns two randomly generated lineups.

        :returns: Lineups with randomly generated players
        :rtype: :class:`ilc_models.Lineups`
        """
        return Lineups(home=self.lineup(), away=self.lineup())

    def team_suffix(self) -> str:
        """Returns a team suffix (United, City, etc.).

        :returns: Randomly selected suffix
        :rtype: str
        """
        suffixes = (
            "Albion",
            "Argyle",
            "Athletic",
            "City",
            "County",
            "Dons",
            "FC",
            "Forest",
            "Hotspur",
            "North End",
            "Orient",
            "Palace",
            "Rangers",
            "Rovers",
            "Swifts",
            "Town",
            "United",
            "Wanderers",
            "Wednesday",
            "",
        )
        return random.choice(suffixes)

    def team(self) -> str:
        """Returns a randomly generated team name.

        :returns: Team name
        :rtype: str
        """
        return " ".join((fake.city(), fake.team_suffix())).rstrip()


def _unique_choices(
    population: MutableSequence[Any], weights: Optional[list[int]] = None, k=1
) -> list[Any]:
    """Return a `k` sized list of elements chosen from the `population` without replacement.

    :param population: Population to select elements from
    :type population: MutableSequence[Any]
    :param weights: If specified, selections are made according to the relative weights (default=None)
    :type weights: MutableSequence[int|float]
    :param k: Number of selections to return (default=1)
    :type k: int
    :returns: Selected elements
    :rtype: list[Any]
    """
    _population = population[:]
    _weights = weights[:] if weights is not None else None

    choices: list[Any] = []
    while len(choices) < k:
        choice = random.choices(_population, weights=_weights)[0]
        choices.append(choice)
        i = _population.index(choice)
        del _population[i]
        if _weights:
            del _weights[i]

    return choices


fake.add_provider(ILCProvider)


@pytest.fixture(scope="session")
def ilc_fake():
    return fake
