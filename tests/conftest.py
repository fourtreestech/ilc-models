import datetime
import random
import pytest
from collections.abc import MutableSequence
from typing import Optional, Any

from faker import Faker
from faker.providers import BaseProvider

from ilc_models import BasePlayer, Lineup, Lineups, Match, Player, Score, Teams

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

    def __str__(self) -> str:
        return f"{self.shirt_number}. {self.base_player.name}{' (GK)' if self.keeper else ''}"


class Team:
    """Randomly generated team."""

    def __init__(self):
        self.name = fake.unique.team_name()
        self.squad = fake.squad()
        self.strength = random.randint(0, 5)

    def __str__(self) -> str:
        return self.name


class ILCProvider(BaseProvider):
    """Faker provider for ILC data models"""

    def player_id(self) -> int:
        """Returns a random player ID.

        :returns: Random player ID between 1 and 99,999
        :rtype: int
        """
        return random.randint(1, 99_999)

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

    def squad(self, size=25, keepers=3) -> list[SquadPlayer]:
        """Returns a randomly generated list of SquadPlayers.

        :param size: Number of players to generate (default=25)
        :type size: int
        :param keepers: Number of goalkeepers to include (default=3)
        :type keepers: int
        :returns: List of randomly generated squad players
        :rtype: list[:class:`SquadPlayer`]
        """
        # Shirt numbers - prefer 2-11, then 12-19 then 20-39
        shirts = list(range(2, 40))
        shirt_weights = [3] * 10 + [2] * 8 + [1] * 20

        # Generate random shirt numbers for this squad
        shirt_numbers = _unique_choices(shirts, weights=shirt_weights, k=size - 1)

        # One goalkeeper will be shirt 1 - select numbers for any others
        keeper_shirts = [1]
        while len(keeper_shirts) < keepers:
            shirt = random.choice([n for n in shirt_numbers if n > 11])
            keeper_shirts.append(shirt)
            shirt_numbers.remove(shirt)

        # Generate squad
        squad = [SquadPlayer(shirt_number=n, keeper=True) for n in keeper_shirts]
        for n in shirt_numbers:
            squad.append(SquadPlayer(shirt_number=n))

        return squad

    def lineup(self, squad: Optional[list[SquadPlayer]] = None) -> Lineup:
        """Returns a randomly generated Lineup.

        Creates a lineup with 11 starting players and 7 substitutes.

        If `squad` is supplied the players will be chosen from the squad,
        otherwise a new set of players will be randomly generated.

        :param squad: Squad players to choose from (default=None)
        :type squad: list[:class:`SquadPlayer`]
        :returns: Lineup with randomly generated players
        :rtype: :class:`ilc_models.Lineup`
        """
        # Get random squad
        if squad is None:
            squad = self.squad(size=18, keepers=2)

        # Decide which goalkeeper will start
        keepers = [p for p in squad if p.keeper]
        keeper_weights = [p.selection_weight for p in keepers]
        keeper1 = random.choices(keepers, weights=keeper_weights)[0]
        keeper2 = [p for p in keepers if p != keeper1][0]

        # Get outfield players
        outfield = [p for p in squad if p not in keepers]
        outfield_weights = [p.selection_weight for p in outfield]
        starting = _unique_choices(outfield, weights=outfield_weights, k=10)

        # Get outfield subs
        remaining = [p for p in outfield if p not in starting]
        remaining_weights = [p.selection_weight for p in remaining]
        subs = _unique_choices(remaining, weights=remaining_weights, k=6)

        # Make lineup
        lineup = Lineup(
            starting=[(keeper1.shirt_number, keeper1.base_player)]
            + [(p.shirt_number, p.base_player) for p in starting],
            subs=[(keeper2.shirt_number, keeper2.base_player)]
            + [(p.shirt_number, p.base_player) for p in subs],
        )

        return lineup

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

    def team_name(self) -> str:
        """Returns a randomly generated team name.

        :returns: Team name
        :rtype: str
        """
        return " ".join((fake.city(), fake.team_suffix())).rstrip()

    def team(self) -> Team:
        """Returns a randomly generated team.

        :returns: Randomly generated team, populated with a squad of players
        :rtype: :class:`Team`
        """
        return Team()

    def match_id(self) -> int:
        """Returns a random match ID.

        :returns: Random match ID between 1 and 999,999
        :rtype: int
        """
        return random.randint(1, 999_999)

    def match(
        self,
        kickoff: Optional[datetime.datetime] = None,
        round="",
        home: Optional[Team] = None,
        away: Optional[Team] = None,
    ) -> Match:
        """Returns a randomly generated match"""
        # Kickoff time if not provided
        if kickoff is None:
            date = fake.past_date(start_date="-1y")
            kickoff = datetime.datetime(
                date.year,
                date.month,
                date.day,
                hour=15,
                tzinfo=datetime.timezone(datetime.timedelta()),
            )

        # Teams if not provided
        if home is None:
            home = fake.team()
        if away is None:
            away = fake.team()

        # Score
        # The score algorithm starts with the strength difference
        # between the two teams
        strength_delta = home.strength - away.strength

        # Weight possible score differences depending on the strength difference
        counts = [12 - abs(n - strength_delta) for n in range(-5, 6)]

        # Select from the weighted score differences
        score_delta = random.sample(range(-5, 6), 1, counts=counts)[0]

        # Convert to an actual score
        # 0 or -1 is a draw, other negative numbers are an away win,
        # positive numbers are a home win
        low_score = random.randint(0, 2)
        if score_delta < 1:
            home_score = low_score
            away_score = (
                home_score
                if score_delta in (0, -1)
                else home_score + abs(score_delta + 1)
            )
        else:
            away_score = low_score
            home_score = away_score + score_delta
        score = Score(home=home_score, away=away_score)

        return Match(
            match_id=fake.unique.match_id(),
            kickoff=kickoff.isoformat(),
            round=round or f"Round {random.randint(1, 38)}",
            teams=Teams(home=home.name, away=away.name),
            status="FT",
            score=score,
        )


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
