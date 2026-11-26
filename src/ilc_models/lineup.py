"""Lineup models."""

from operator import itemgetter

from pydantic import BaseModel, Field

from .player import BasePlayer


class Lineup(BaseModel):
    """Lineup for one team.

    Each lineup entry is an (int, BasePlayer) tuple, with the int
    being the player's shirt number if supplied (0 if not).

    Attributes:
        starting: Starting XI, at most 11 players (default=[]).
        subs: Substitutes (default=[]).
    """

    starting: list[tuple[int, BasePlayer]] = Field(max_length=11, default=[])
    subs: list[tuple[int, BasePlayer]] = []

    def __bool__(self) -> bool:
        """Return True if this lineup is populated with players.

        Returns:
            `True` if this lineup contains at least one player.
        """
        return len(self.starting) + len(self.subs) > 0

    def sort(self) -> None:
        """Sort the lineup.

        Each part of the lineup is sorted by shirt number, except
        for the first item in the starting lineup which is
        assumed to be the goalkeeper and is left as the first item.
        """
        self.starting = self.starting[:1] + sorted(self.starting[1:], key=itemgetter(0))
        self.subs.sort(key=itemgetter(0))

    def players(self) -> list[BasePlayer]:
        """Return all players in this lineup.

        Returns:
            Every player in the starting XI and on the bench.
        """
        return [p[1] for p in self.starting] + [p[1] for p in self.subs]

    def __len__(self) -> int:
        """Return the total number of players in this lineup.

        Returns:
            The total number of players in this lineup.
        """
        return len(self.starting) + len(self.subs)


class Lineups(BaseModel):
    """Match lineups for home and away teams.

    Attributes:
        home: Home lineup (default=`Lineup()`).
        away: Away lineup (default=`Lineup()`).
    """

    home: Lineup = Lineup()
    away: Lineup = Lineup()

    def __bool__(self) -> bool:
        """Return True if either lineup is populated with players.

        Returns:
            `True` if the home or away lineup contains at least one player.
        """
        return bool(self.home) or bool(self.away)

    def sort(self) -> None:
        """Sort the lineups.

        Each part of the lineup is sorted by shirt number, except
        for the first item in the starting lineup which is
        assumed to be the goalkeeper and is left as the first item.
        """
        self.home.sort()
        self.away.sort()

    def players(self) -> list[BasePlayer]:
        """Return all players in these lineups.

        Returns:
            Every player in the home and away lineups.
        """
        return self.home.players() + self.away.players()

    def __len__(self) -> int:
        """Return the total number of players in these lineups.

        Returns:
            The total number of players in these lineups.
        """
        return len(self.home) + len(self.away)
