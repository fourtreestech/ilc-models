"""Tests for match models"""

import datetime
import random

import pytest
from pydantic import ValidationError

from ilc_models import (
    Card,
    EventTime,
    Goal,
    Lineups,
    Match,
)


class TestMatch:
    def test_match_returns_played_true(self, ilc_fake):
        match = ilc_fake.match()
        assert match.played

    def test_match_date(self, ilc_fake):
        kickoff = datetime.datetime(
            2025, 2, 1, 15, tzinfo=datetime.timezone(datetime.timedelta())
        )
        match = ilc_fake.match(kickoff=kickoff)
        assert match.date == datetime.date(2025, 2, 1)

    def test_kickoff_rejects_invalid_date_format(self, ilc_fake):
        match = ilc_fake.match()
        match_dict = match.model_dump()

        # Set to invalid format ('T' swapped out for '-')
        match_dict["kickoff"] = "2024-06-08-15:00:00+00:00"
        with pytest.raises(ValidationError):
            Match(**match_dict)

    def test_kickoff_rejects_impossible_date(self, ilc_fake):
        match = ilc_fake.match()
        match_dict = match.model_dump()
        match_dict["kickoff"] = "2024-02-30T15:00:00+00:00"
        with pytest.raises(ValidationError):
            Match(**match_dict)

    def test_kickoff_rejects_impossible_time(self, ilc_fake):
        match = ilc_fake.match()
        match_dict = match.model_dump()
        match_dict["kickoff"] = "2024-06-08T25:00:00+00:00"
        with pytest.raises(ValidationError):
            Match(**match_dict)

    def test_involves(self, ilc_fake):
        home = ilc_fake.team()
        away = ilc_fake.team()
        other = ilc_fake.team()
        match = ilc_fake.match(home=home, away=away)
        assert match.involves(home.name)
        assert match.involves(away.name)
        assert not match.involves(other.name)

    def test_involves_any(self, ilc_fake):
        home = ilc_fake.team()
        away = ilc_fake.team()
        other = ilc_fake.team()
        match = ilc_fake.match(home=home, away=away)
        assert match.involves_any([home.name])
        assert match.involves_any([away.name])
        assert match.involves_any([home.name, away.name])
        assert match.involves_any([other.name, away.name])
        assert not match.involves_any([other.name])

    def test_h2h(self, ilc_fake):
        home = ilc_fake.team()
        away = ilc_fake.team()
        other = ilc_fake.team()
        match = ilc_fake.match(home=home, away=away)
        assert match.h2h(home.name, away.name)
        assert match.h2h(away.name, home.name)
        assert not match.h2h(home.name, home.name)
        assert not match.h2h(other.name, home.name)

    def test_events_returns_all_events(self, ilc_fake):
        match = ilc_fake.match()
        assert len(match.events()) == len(match.goals) + len(match.cards) + len(
            match.substitutions
        )

    def test_events_are_in_time_order(self, ilc_fake):
        events = ilc_fake.match().events()
        previous = None
        for event in events:
            if previous:
                assert event.time >= previous
            previous = event.time

    def test_delete_event(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.goals and match.cards and match.substitutions:
                break

        while match.events():
            event = random.choice(match.events())
            count = match.events().count(event)
            total = len(match.events())
            match.delete_event(event)
            assert match.events().count(event) == count - 1
            assert len(match.events()) == total - 1

    def test_delete_event_raises_value_error(self, ilc_fake):
        match = ilc_fake.match()
        event = ilc_fake.goal()
        assert event not in match.events()
        with pytest.raises(ValueError):
            match.delete_event(event)

    def test_replace_event_replaces_goal(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.goals:
                break

        player = ilc_fake.base_player()
        old = match.goals[0]
        new = old.model_copy(deep=True)
        new.scorer = player
        match.replace_event(old, new)
        assert old not in match.goals
        assert new in match.goals

    def test_replace_goal_with_card_raises_type_error(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.goals:
                break

        old = match.goals[0]
        new = ilc_fake.card()
        with pytest.raises(TypeError):
            match.replace_event(old, new)

    def test_replace_event_replaces_card(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.cards:
                break

        player = ilc_fake.base_player()
        old = match.cards[0]
        new = old.model_copy(deep=True)
        new.player = player
        match.replace_event(old, new)
        assert old not in match.cards
        assert new in match.cards

    def test_replace_card_with_goal_raises_type_error(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.cards:
                break

        old = match.cards[0]
        new = ilc_fake.goal()
        with pytest.raises(TypeError):
            match.replace_event(old, new)

    def test_replace_event_replaces_sub(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.substitutions:
                break

        old = match.substitutions[0]
        new = old.model_copy(deep=True)
        new.player_off, new.player_on = old.player_on, old.player_off
        match.replace_event(old, new)
        assert old not in match.substitutions
        assert new in match.substitutions

    def test_replace_sub_with_goal_raises_type_error(self, ilc_fake):
        while True:
            match = ilc_fake.match()
            if match.substitutions:
                break

        old = match.substitutions[0]
        new = ilc_fake.goal()
        with pytest.raises(TypeError):
            match.replace_event(old, new)

    def test_players_returns_list_of_correct_length(self, ilc_fake):
        match = ilc_fake.match()
        assert len(match.players()) == len(match.lineups)

    def test_players_sourced_from_events(self, ilc_fake):
        match = ilc_fake.match()
        match.lineups = Lineups()
        assert match.players()

    def test_players_from_team(self, ilc_fake):
        match = ilc_fake.match()
        team = match.teams.home
        players = match.players(team=team)
        for player in match.lineups.home.starting:
            assert player[1] in players
        for player in match.lineups.away.starting:
            assert player[1] not in players

    def test_team_players_from_events(self, ilc_fake):
        match = ilc_fake.match()
        match.lineups = Lineups()
        team = match.teams.home
        players = match.players(team=team)
        for event in match.events():
            if match.event_team(event) == team:
                for player in event.players():
                    assert player in players

    def test_returns_players_from_teams(self, ilc_fake):
        match = ilc_fake.match()
        players = match.players(teams=[match.teams.home, match.teams.away])
        for player in match.lineups.home.starting:
            assert player[1] in players
        for player in match.lineups.away.starting:
            assert player[1] in players

    def test_returns_only_players_from_specified_teams(self, ilc_fake):
        match = ilc_fake.match()
        players = match.players(teams=[match.teams.home, "Non-existent United"])
        for player in match.lineups.home.starting:
            assert player[1] in players
        for player in match.lineups.away.starting:
            assert player[1] not in players

    def test_returns_no_players_if_teams_arent_in_the_match(self, ilc_fake):
        match = ilc_fake.match()
        players = match.players(teams=["Non-existent United"])
        assert not players

    def test_own_goal_scorer_to_correct_team(self, ilc_fake):
        home = ilc_fake.team()
        away = ilc_fake.team()
        match = ilc_fake.match(home=home, away=away)
        home_players = [player[1] for player in match.lineups.home.starting]
        away_players = [player[1] for player in match.lineups.away.starting]
        match.cards = []
        match.substitutions = []

        # Generate an own goal for the home team
        match.goals = [
            ilc_fake.goal(
                team=home,
                goal_type="O",
                players=(home_players, away_players),
            )
        ]
        match.lineups = Lineups()

        # There should be one away player returned
        assert not match.players(team=match.teams.home)
        players = match.players(team=match.teams.away)
        assert len(players) == 1
        assert players[0] in away_players

    def test_invalid_team_returns_empty_list(self, ilc_fake):
        match = ilc_fake.match()
        assert not match.players(team="ABCDEFG")

    def test_event_team_returns_event_team_for_normal_goal(self, ilc_fake):
        match = ilc_fake.match()
        goal = Goal(
            team=match.teams.home,
            time=EventTime(minutes=45),
            scorer=ilc_fake.base_player(),
        )
        assert match.event_team(goal) == match.teams.home

    def test_event_team_flips_home_own_goal(self, ilc_fake):
        match = ilc_fake.match()
        goal = Goal(
            team=match.teams.home,
            time=EventTime(minutes=45),
            goal_type="O",
            scorer=ilc_fake.base_player(),
        )
        assert match.event_team(goal) == match.teams.away

    def test_event_team_flips_away_own_goal(self, ilc_fake):
        match = ilc_fake.match()
        goal = Goal(
            team=match.teams.away,
            time=EventTime(minutes=45),
            goal_type="O",
            scorer=ilc_fake.base_player(),
        )
        assert match.event_team(goal) == match.teams.home

    def test_event_team_returns_event_team_for_card(self, ilc_fake):
        match = ilc_fake.match()
        card = Card(
            team=match.teams.away,
            time=EventTime(minutes=45),
            color="Y",
            player=ilc_fake.base_player(),
        )
        assert match.event_team(card) == match.teams.away

    def test_played_for_returns_correct_team_from_lineup(self, ilc_fake):
        match = ilc_fake.match()
        team = random.choice((match.teams.home, match.teams.away))
        lineup = match.lineups.home if team == match.teams.home else match.lineups.away
        player = random.choice(lineup.players())
        assert match.played_for(player) == team

    def test_played_for_returns_correct_team_from_event(self, ilc_fake):
        # Get a match with at least one event
        while True:
            match = ilc_fake.match()
            if match.events():
                break

        # Remove lineups
        match.lineups = Lineups()

        # Select an event and player
        event = random.choice(match.events())
        player = random.choice(event.players())
        team = match.event_team(event)

        # Check returns the correct team
        assert match.played_for(player) == team

    def test_played_for_returns_empty_string(self, ilc_fake):
        match = ilc_fake.match()
        player = ilc_fake.base_player()
        # ilc-provider only generates IDs up to 999,999
        # so ensure this player won't clash with a genuine player ID
        # in this match by making the ID >1,000,000
        player.player_id = random.randint(1_000_000, 9_999_999)
        assert match.played_for(player) == ""

    def test_str_gives_score(self, ilc_fake):
        match = ilc_fake.match()
        assert " - ".join((str(match.score.home), str(match.score.away))) in str(match)

    def test_str_unplayed_gives_vs(self, ilc_fake):
        match = ilc_fake.match(status="NS")
        assert " vs " in str(match)
