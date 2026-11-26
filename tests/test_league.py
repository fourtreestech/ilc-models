"""Tests for league models"""

import datetime
import itertools
import random

import pytest
from pydantic import ValidationError

from ilc_models import (
    Card,
    Deduction,
    EventTime,
    Goal,
    League,
    Lineups,
    Substitution,
)


class TestLeague:
    def test_title(self, fake_league):
        title = fake_league.title
        assert fake_league.name in title
        assert fake_league.start[:4] in title

    def test_league_rejects_impossible_start_date(self, ilc_fake):
        league_dict = ilc_fake.league().model_dump()
        league_dict["start"] = "2020-19-39"
        with pytest.raises(ValidationError):
            League(**league_dict)

    def test_matches_sorted_by_date(self, fake_league):
        matches = fake_league.matches()
        previous = None
        for match in matches:
            if previous is not None:
                assert match.date >= previous.date
            previous = match

    def test_matches_filtered_by_team(self, fake_league):
        team = random.choice(fake_league.teams)
        matches = fake_league.matches(team=team)
        for match in matches:
            assert match.teams.home == team or match.teams.away == team

    def test_matches_filtered_by_teams(self, fake_league):
        teams = random.sample(fake_league.teams, k=3)
        matches = fake_league.matches(teams=teams)
        for match in matches:
            assert any(team in (match.teams.home, match.teams.away) for team in teams)

    def test_matches_filtered_by_h2h(self, fake_league):
        teams = tuple(random.sample(fake_league.teams, k=2))
        matches = fake_league.matches(h2h=teams)
        for match in matches:
            assert all(team in (match.teams.home, match.teams.away) for team in teams)

    def test_matches_filtered_by_player(self, fake_league):
        match = random.choice(fake_league.matches())
        player = random.choice(match.players())
        matches = fake_league.matches(player=player)
        assert match in matches
        assert all(player in m.players() for m in matches)

    def test_events_returns_correct_players_events(self, fake_league):
        player = None
        for match in fake_league.matches():
            for goal in match.goals:
                player = goal.scorer
                break
            if player is not None:
                break

        events = fake_league.events(player=player)
        for event_info in events:
            assert player in event_info.event.players()

    def test_events_returns_lineup_status(self, fake_league):
        match = random.choice(fake_league.matches())
        player = random.choice(match.lineups.home.starting)[1]
        events = fake_league.events(player)
        for event in events:
            if event.date == match.date and event.event.event_type == "status":
                assert event.event.status == "starting"
                break
        else:  # pragma: no cover
            raise AssertionError()

    def test_update_player(self, ilc_fake, fake_league):
        # Find a player
        player = None
        for match in fake_league.matches():
            for goal in match.goals:
                player = goal.scorer
                break
            if player is not None:
                break

        # Old player has events - new player doesn't
        old = player
        new = ilc_fake.base_player()
        old_events = fake_league.events(player=old)
        assert old_events
        assert not fake_league.events(player=new)

        # Swap out old player for new
        fake_league.update_player(old, new)

        # Now new player should have events, old player shouldn't
        new_events = fake_league.events(player=new)
        assert len(new_events) == len(old_events)
        assert not fake_league.events(player=old)

    def test_update_player_on_team(self, fake_league):
        league = fake_league.model_copy(deep=True)

        # Find two players from different teams
        player1 = None
        player2 = None
        team1 = ""
        team2 = ""
        for match in league.matches():
            for goal in match.goals:
                if goal.goal_type != "O":
                    if player1 is None:
                        player1 = goal.scorer
                        team1 = goal.team
                    elif goal.team != team1:
                        player2 = goal.scorer
                        team2 = goal.team
                        break
            if player2:
                break

        # Update so that player2 instances now refer to player1
        league.update_player(player2, player1)
        assert not league.events(player=player2)

        # Now switch back so that team1 events actually have player2
        # and team2 events will have player1
        league.update_player(player1, player2, team=team1)
        found1 = False
        found2 = False
        for match in league.matches():
            if match.involves(team1):
                for goal in match.goals:
                    if goal.goal_type != "O" and goal.team == team1:
                        assert goal.scorer != player1
                        found2 = found2 or goal.scorer == player2
            if match.involves(team2):
                for goal in match.goals:
                    if goal.goal_type != "O" and goal.team == team2:
                        assert goal.scorer != player2
                        found1 = found1 or goal.scorer == player1
            if found1 and found2:
                break

        # Should have found player1 scoring for team2
        # and player2 scoring for team1
        assert found1
        assert found2

    def test_player_teams(self, fake_league):
        # Find a player
        player = None
        team = ""
        for match in fake_league.matches():
            for goal in match.goals:
                if goal.goal_type != "O":
                    player = goal.scorer
                    team = goal.team
                    break
            if player is not None:
                break

        # Get teams played for
        teams = fake_league.player_teams(player)
        assert team in teams

    def test_player_teams_finds_player_from_goal(self, ilc_fake):
        player = ilc_fake.base_player()
        league = ilc_fake.league(matches=False)
        m = ilc_fake.match()
        m.goals.append(
            Goal(
                team=m.teams.home,
                time=EventTime(minutes=45),
                goal_type="N",
                scorer=player,
            )
        )
        m.lineups = Lineups()
        league.rounds = {"Round 1": [m]}
        assert m.teams.home in league.player_teams(player)

    def test_player_teams_finds_player_from_own_goal(self, ilc_fake):
        player = ilc_fake.base_player()
        league = ilc_fake.league(matches=False)
        m = ilc_fake.match()
        m.goals.append(
            Goal(
                team=m.teams.home,
                time=EventTime(minutes=45),
                goal_type="O",
                scorer=player,
            )
        )
        m.lineups = Lineups()
        league.rounds = {"Round 1": [m]}
        assert m.teams.away in league.player_teams(player)

    def test_player_teams_finds_player_from_card(self, ilc_fake):
        player = ilc_fake.base_player()
        league = ilc_fake.league(matches=False)
        m = ilc_fake.match()
        m.cards.append(
            Card(
                team=m.teams.home, time=EventTime(minutes=45), color="Y", player=player
            )
        )
        m.lineups = Lineups()
        league.rounds = {"Round 1": [m]}
        assert m.teams.home in league.player_teams(player)

    def test_player_teams_finds_player_from_substitution(self, ilc_fake):
        player = ilc_fake.base_player()
        player2 = ilc_fake.base_player()
        league = ilc_fake.league(matches=False)
        m = ilc_fake.match()
        m.substitutions.append(
            Substitution(
                team=m.teams.home,
                time=EventTime(minutes=45),
                player_off=player,
                player_on=player2,
            )
        )
        m.lineups = Lineups()
        league.rounds = {"Round 1": [m]}
        assert m.teams.home in league.player_teams(player)

    def test_head_to_head(self, ilc_fake):
        league = ilc_fake.league(team_count=8, games_per_opponent=2, split_mode="none")
        for t1, t2 in itertools.permutations(league.teams, r=2):
            assert len(league.head_to_head((t1, t2))) == 2

    def test_match_players_includes_all_players(self, fake_league):
        players = fake_league.match_players()
        # Select a random player from a random match
        # and check he is in the players list
        match = random.choice(fake_league.matches())
        player = random.choice(match.players())
        assert player in players

    def test_match_players_includes_no_duplicates(self, fake_league):
        players = fake_league.match_players()
        ids = {player.player_id for player in players}
        assert len(ids) == len(players)

    def test_match_players_returns_for_team(self, fake_league):
        team = random.choice(fake_league.teams)
        players = fake_league.match_players(team=team)
        matches = fake_league.matches(team=team)
        match = random.choice(matches)
        # All players featuring for team in this match
        # should be in the player list
        lineup = match.lineups.home if team == match.teams.home else match.lineups.away
        for player in lineup.starting:
            assert player[1] in players
        for player in lineup.subs:
            assert player[1] in players

    def test_match_players_returns_for_teams(self, fake_league):
        match = random.choice(fake_league.matches())
        players = fake_league.match_players(teams=[match.teams.home, match.teams.away])
        for player in match.players():
            assert player in players

    def test_match_players_returns_for_h2h(self, fake_league):
        match = random.choice(fake_league.matches())
        players = fake_league.match_players(h2h=(match.teams.home, match.teams.away))
        for player in match.players():
            assert player in players


class TestLeagueTable:
    def test_league_table_is_correct_size(self, fake_league):
        table = fake_league.table()
        assert len(table) == len(fake_league.teams)

    def test_all_teams_have_played_the_same_number_of_matches(self, fake_league):
        table = fake_league.table()
        played = table[0].played
        assert all(row.played == played for row in table)

    def test_all_teams_are_in_the_league_table(self, fake_league):
        table = fake_league.table()
        assert all(row.team in fake_league.teams for row in table)

    def test_table_is_correctly_ordered(self, fake_league):
        table = fake_league.table()
        # Skip mid-point if there is a league split
        skip = (len(table) // 2) if fake_league.split else 0
        for n in range(1, len(table)):  # pragma: no cover
            if n != skip:
                previous = table[n - 1]
                row = table[n]
                assert row.points <= previous.points
                if row.points == previous.points:
                    assert row.gd <= previous.gd
                    if row.gd == previous.gd:
                        assert row.goals_for <= previous.goals_for
                        if row.goals_for == previous.goals_for:
                            assert row.team >= previous.team

    def test_table_on_date(self, fake_league):
        # Find out how many matches are played on the opening day
        matches = fake_league.matches()
        date = matches[0].date
        matches_on_date = sum(1 for match in matches if match.date == date)

        # Get the league table on that date
        # Total of 'played' column should be twice the number of matches played
        table = fake_league.table(date=date)
        played = sum(row.played for row in table)
        assert played == matches_on_date * 2

    def test_table_with_matches_played(self, fake_league):
        table = fake_league.table(played=10)
        assert all(row.played >= 10 for row in table)

    def test_table_at_split(self, ilc_fake):
        league = ilc_fake.league(
            team_count=6, games_per_opponent=4, split_mode="fixed", games_before_split=3
        )
        table = league.table(split_point=True)
        assert all(row.played == 15 for row in table)

    def test_handles_deduction(self, ilc_fake):
        league = ilc_fake.league(team_count=6)
        table = league.table()
        team = table[0].team
        points = table[0].points

        league.deductions = [Deduction(team=team, points=10)]
        table = league.table()
        for row in table:
            if row.team == team:
                assert row.points == points - 10
                break

    def test_populates_form(self, fake_league):
        table = fake_league.table()
        matches = fake_league.matches()
        last_match = matches[-1]
        team = last_match.teams.home
        if last_match.score.home > last_match.score.away:  # pragma: no cover
            result = "W"
        elif last_match.score.home < last_match.score.away:  # pragma: no cover
            result = "L"
        else:  # pragma: no cover
            result = "D"

        for row in table:
            if row.team == team:
                assert row.form[-1] == result
                break
        else:  # pragma: no cover
            raise AssertionError(f"Team {team} not found in table {table}")

    def test_handles_deduction_with_date(self, ilc_fake):
        league = ilc_fake.league(team_count=6)

        # Find a date midway through the league
        start = datetime.date.fromisoformat(league.start)
        end = datetime.date.fromisoformat(league.end)
        delta = (end - start).days
        deduction_date = (start + datetime.timedelta(days=(delta // 2))).isoformat()[
            :10
        ]

        # Get a team and deduct 10 points
        team = league.teams[0]
        league.deductions = [Deduction(team=team, points=10, date=deduction_date)]

        # Get one day before and after the deduction date
        date = datetime.date.fromisoformat(deduction_date)
        pre_date = date - datetime.timedelta(days=1)
        post_date = date + datetime.timedelta(days=1)

        # Get points the day before the deduction
        table = league.table(date=pre_date)
        pre_points = 0
        for row in table:
            if row.team == team:
                pre_points = row.points
                break

        # Get points the day after the deduction
        table = league.table(date=post_date)
        post_points = 0
        for row in table:
            if row.team == team:
                post_points = row.points
                break

        # There should be a reduction in points
        assert post_points < pre_points
