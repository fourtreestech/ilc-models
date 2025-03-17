import datetime
import random
import pytest
from collections.abc import MutableSequence
from operator import attrgetter
from typing import Optional, Any, cast, Literal

from faker import Faker
from faker.providers import BaseProvider

from ilc_models import (
    BasePlayer,
    Card,
    Event,
    Goal,
    Lineup,
    Lineups,
    Match,
    Player,
    Score,
    Substitution,
    Teams,
)

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

    def lineups(
        self,
        home_squad: Optional[list[SquadPlayer]] = None,
        away_squad: Optional[list[SquadPlayer]] = None,
    ) -> Lineups:
        """Returns two randomly generated lineups.

        If `home_squad` or `away_squad` is supplied the players will be chosen from the squads,
        otherwise new sets of players will be randomly generated.

        :param home_squad: Squad players for the home team (default=None)
        :type home_squad: list[:class:`SquadPlayer`]
        :param away_squad: Squad players for the home team (default=None)
        :type away_squad: list[:class:`SquadPlayer`]
        :returns: Lineups with randomly generated players
        :rtype: :class:`ilc_models.Lineups`
        """
        return Lineups(home=self.lineup(home_squad), away=self.lineup(away_squad))

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
        round: Optional[str] = None,
        home: Optional[Team] = None,
        away: Optional[Team] = None,
        status: Optional[str] = None,
    ) -> Match:
        """Returns a randomly generated match.

        Takes a number of optional parameters which if supplied
        will be added to the match. Any parameters not
        supplied will be randomly generated.

        :param kickoff: Kickoff time (default=None)
        :type kickoff: :class:`datetime.datetime`
        :param round: Round this match is part of (default=None)
        :type round: str
        :param home: Home team (default=None)
        :type home: :class:`Team`
        :param away: Away team (default=None)
        :type away: :class:`Team`
        :param status: Match status (default=None)
        :type status: str
        """
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

        # Create match object
        match = Match(
            match_id=fake.unique.match_id(),
            kickoff=kickoff.isoformat(),
            round=round or f"Round {random.randint(1, 38)}",
            teams=Teams(home=home.name, away=away.name),
            status=status or "FT",
        )

        if match.played:
            # Score - start with the strength difference
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
            match.score = Score(home=home_score, away=away_score)

            # Lineups
            match.lineups = self.lineups(home_squad=home.squad, away_squad=away.squad)

            # Substitutions
            for team, lineup in zip(
                (home, away), (match.lineups.home, match.lineups.away)
            ):
                # Exclude goalkeepers from substitutions
                keepers = [p.base_player for p in team.squad if p.keeper]
                possible_exits = [p[1] for p in lineup.starting if p[1] not in keepers]
                possible_entries = [p[1] for p in lineup.subs if p[1] not in keepers]

                total_subs = random.randint(1, min(5, len(possible_entries)))
                subs: list[Event] = []
                windows_used = 0

                while (
                    len(subs) < total_subs
                    and len(possible_entries) > 0
                    and len(possible_exits) > 0
                ):
                    # Get sub window
                    window_subs = self.sub_window(
                        team.name,
                        total_subs - len(subs) if windows_used == 2 else 0,
                        0,
                        0,
                        possible_exits,
                        possible_entries,
                    )

                    # Remove players used
                    for sub in window_subs:
                        detail = cast(Substitution, sub.detail)
                        possible_entries.remove(detail.player_on)
                        possible_exits.remove(detail.player_off)

                    subs += window_subs

                match.substitutions.extend(subs[:total_subs])

            # Cards
            for team, lineup in zip(
                (home, away), (match.lineups.home, match.lineups.away)
            ):
                # 0-4 cards per team per match
                for _ in range(random.randint(0, 4)):
                    # Generate card
                    time, plus = self.event_time()
                    players = players_on(
                        team.name,
                        [p[1] for p in lineup.starting],
                        match.events(),
                        time,
                        plus,
                    )
                    card = self.card(team.name, time, plus, players)

                    # Check for second yellow
                    card_detail = cast(Card, card.detail)
                    if card_detail.color == "Y":
                        for card2 in match.cards:
                            detail2 = cast(Card, card2.detail)
                            if (
                                detail2.color == "Y"
                                and detail2.player == card_detail.player
                            ):
                                # Find which is the second card
                                if card.time == card2.time:
                                    max_time = card.time
                                    max_plus = max(card.plus, card2.plus)
                                elif card.time > card2.time:
                                    max_time = card.time
                                    max_plus = card.plus
                                else:
                                    max_time = card2.time
                                    max_plus = card2.plus
                                match.cards.append(card)
                                card = Event(
                                    team=team.name,
                                    time=max_time,
                                    plus=max_plus,
                                    detail=Card(color="R", player=card_detail.player),
                                )
                                break

                    match.cards.append(card)

                    # Red card - check player isn't subbed off later
                    card_detail = cast(Card, card.detail)
                    if card_detail.color == "R":
                        sub_index = -1
                        for i, sub in enumerate(match.substitutions):
                            sub_detail = cast(Substitution, sub.detail)
                            if card_detail.player == sub_detail.player_off:
                                sub_index = i
                                break
                        if sub_index != -1:
                            del match.substitutions[sub_index]

            # Goals
            for (
                scoring_team,
                other_team,
                scoring_lineup,
                other_lineup,
                goal_count,
            ) in zip(
                (home, away),
                (away, home),
                (match.lineups.home, match.lineups.away),
                (match.lineups.away, match.lineups.home),
                (match.score.home, match.score.away),
            ):
                for _ in range(goal_count):
                    time, plus = self.event_time()
                    scoring_team_players = players_on(
                        scoring_team.name,
                        [p[1] for p in scoring_lineup.starting],
                        match.events(),
                        time,
                        plus,
                    )
                    other_team_players = players_on(
                        other_team.name,
                        [p[1] for p in other_lineup.starting],
                        match.events(),
                        time,
                        plus,
                    )
                    match.goals.append(
                        self.goal(
                            scoring_team,
                            time,
                            plus,
                            (scoring_team_players, other_team_players),
                        )
                    )

        return match

    def sub_window(
        self,
        team: Optional[str] = None,
        sub_count: int = 0,
        time: int = 0,
        plus: int = 0,
        possible_exits: Optional[list[BasePlayer]] = None,
        possible_entries: Optional[list[BasePlayer]] = None,
    ) -> list[Event]:
        """Returns a randomly generated list of substitutions made within a single window.

        Any paramters not supplied will be randomly generated.

        :param team: Name of the team making this substitution (default=None)
        :type team: str
        :param sub_count: Number of substitutions to be made in this window (default=0)
        :type sub_count: str
        :param time: Time of the substitution (default=0)
        :type time: int
        :param plus: Plus time of the substitution (default=0)
        :type plus: int
        :param possible_exits: Players who can come off the field (default=None)
        :type possible_exits: list[BasePlayer]
        :param possible_entries: Players who can come on the field (default=None)
        :type possible_entris: list[BasePlayer]
        :returns: Randomly generated substitutions
        :rtype: list[:class:`Event`]
        """
        if team is None:
            team = self.team_name()

        if sub_count == 0:
            max_subs = len(possible_exits) if possible_exits else 3
            sub_count = random.randint(1, max_subs)

        if time == 0:
            # Subs are much more likely in the second half
            time, plus = self.event_time(first_half_weighting=10)

        # Players to come on/off
        exits = (
            possible_exits[:]
            if possible_exits
            else [self.base_player() for _ in range(sub_count)]
        )
        entries = (
            possible_entries[:]
            if possible_entries
            else [self.base_player() for _ in range(sub_count)]
        )

        # Generate subs list
        subs: list[Event] = []
        while len(subs) < sub_count:
            sub = self.substitution(team, time, plus, exits, entries)
            detail = cast(Substitution, sub.detail)
            exits.remove(detail.player_off)
            entries.remove(detail.player_on)
            subs.append(sub)
            if len(entries) == 0 or len(exits) == 0:
                break

        return subs

    def substitution(
        self,
        team: Optional[str] = None,
        time: int = 0,
        plus: int = 0,
        possible_exits: Optional[list[BasePlayer]] = None,
        possible_entries: Optional[list[BasePlayer]] = None,
    ) -> Event:
        """Returns a randomly generated substitution.

        Any paramters not supplied will be randomly generated.

        :param team: Name of the team making this substitution (default=None)
        :type team: str
        :param time: Time of the substitution (default=0)
        :type time: int
        :param plus: Plus time of the substitution (default=0)
        :type plus: int
        :param possible_exits: Players who can come off the field (default=None)
        :type possible_exits: list[BasePlayer]
        :param possible_entries: Players who can come on the field (default=None)
        :type possible_entris: list[BasePlayer]
        :returns: Randomly generated substitution
        :rtype: :class:`Event`
        """
        if team is None:
            team = self.team_name()

        if time == 0:
            # Subs are much more likely in the second half
            time, plus = self.event_time(first_half_weighting=10)

        if not possible_exits:
            possible_exits = [self.base_player()]

        if not possible_entries:
            possible_entries = [self.base_player()]

        return Event(
            team=team,
            time=time,
            plus=plus,
            detail=Substitution(
                player_on=random.choice(possible_entries),
                player_off=random.choice(possible_exits),
            ),
        )

    def card(
        self,
        team: Optional[str] = None,
        time: int = 0,
        plus: int = 0,
        players: Optional[list[BasePlayer]] = None,
    ) -> Event:
        """Returns a randomly generated red or yellow card.

        Any paramters not supplied will be randomly generated.

        :param team: Name of the team receiving this card (default=None)
        :type team: str
        :param time: Time of the card (default=0)
        :type time: int
        :param plus: Plus time of the card (default=0)
        :type plus: int
        :param players: Players who can receive the card (default=None)
        :type players: list[BasePlayer]
        :returns: Randomly generated card event
        :rtype: :class:`Event`
        """
        if team is None:
            team = self.team_name()

        if time == 0:
            time, plus = self.event_time()

        if not players:
            players = [self.base_player()]

        # 1 in 30 cards given is a straight red
        color: Literal["Y", "R"] = "R" if random.randint(1, 30) == 30 else "Y"
        player = random.choice(players)

        return Event(
            team=team, time=time, plus=plus, detail=Card(color=color, player=player)
        )

    def goal(
        self,
        team: Optional[Team] = None,
        time: int = 0,
        plus: int = 0,
        players: Optional[tuple[list[BasePlayer], list[BasePlayer]]] = None,
    ) -> Event:
        """Returns a randomly generated goal.

        Any paramters not supplied will be randomly generated.

        :param team: Team scoring this goal (default=None)
        :type team: :class:`Team`
        :param time: Time of the goal (default=0)
        :type time: int
        :param plus: Plus time of the goal (default=0)
        :type plus: int
        :param players: Players who can score the goal as a two-item tuple,
                        the scoring team's players are the first item and
                        the opposing team's players (for own goals) are the
                        second item (default=None)
        :type players: tuple[list[BasePlayer], list[BasePlayer]]
        :returns: Randomly generated goal event
        :rtype: :class:`Event`
        """
        if team is None:
            team = self.team()

        if time == 0:
            time, plus = self.event_time()

        # 1 in 10 goals is a penalty
        # 1 in 30 goals is an own goal
        goal_type: Literal["N", "O", "P"] = "N"
        if random.randint(1, 10) == 10:
            goal_type = "P"
        elif random.randint(1, 30) == 30:
            goal_type = "O"

        # Own goal
        if goal_type == "O":
            if players is None:
                scorer = self.base_player()
            else:
                scorer = random.choice(players[1])

        # Penalty or normal goal
        else:
            if players is None:
                lineup = self.lineup(team.squad)
                players = ([p[1] for p in lineup.starting], [])
            # Select scorer
            potential_scorers = [p for p in team.squad if p.base_player in players[0]]
            potential_scorers.sort(key=attrgetter("scorer_weight"), reverse=True)

            # Penalty is scored by the top weighted scorer
            if goal_type == "P":
                scorer = potential_scorers[0].base_player
            else:
                scorer = random.choices(
                    [p.base_player for p in potential_scorers],
                    [p.scorer_weight for p in potential_scorers],
                    k=1,
                )[0]

        return Event(
            team=team.name,
            time=time,
            plus=plus,
            detail=Goal(goal_type=goal_type, scorer=scorer),
        )

    def event_time(self, first_half_weighting=50) -> tuple[int, int]:
        """Returns a randomly generated event time.

        The ``first_half_weighting`` parameter controls how likely it is
        that the time will be in the first half. A value of 50 means
        either half will have equal probability; higher values increase
        the likelihood of a first half time.

        The time is returned as a (time, plus) tuple e.g.
        27' is returned as ``(27, 0)`` while 90+3' will be returned
        as ``(90, 3)``.

        :param first_half_weighting: Weight / 100 to give to a time in the first half
        :type first_half_weighting: int
        :returns: Randomly generated tuple of (time, plus)
        :rtype: tuple[int, int]
        """
        half = 0 if random.randint(1, 100) <= first_half_weighting else 1
        minute = random.randint(1, 50)
        time = min(minute, 45) + 45 * half
        plus = max(minute - 45, 0)
        return (time, plus)


def players_on(
    team: str, starting: list[BasePlayer], events: list[Event], time: int, plus: int
) -> list[BasePlayer]:
    """Returns the list of players on the pitch at a given time.

    :param team: Team name
    :type team: str
    :param starting: Starting XI
    :type starting: list[:class:`BasePlayer`]
    :param events: Match events
    :type events: list[:class:`Events`]
    :param time: Time to check
    :type time: int
    :param plus: Plus time to check
    :type plus: int
    """
    # Starting lineup
    players = starting[:]

    # Adjust according to events
    for event in events:
        # Check if event has occurred at the given time
        if event.team == team and (
            event.time < time or (event.time == time and event.plus < plus)
        ):
            match event.detail:
                # Adjust for subs
                case Substitution(player_on=player_on, player_off=player_off):
                    players.remove(player_off)
                    players.append(player_on)

                # Remove any players sent off
                case Card(player=player, color=color):
                    if color == "R":
                        players.remove(player)

    return players


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
