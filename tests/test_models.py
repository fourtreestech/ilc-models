"""Tests for data models"""

import datetime
import itertools
import random

import pytest
from pydantic import ValidationError

from ilc_models import (
    BasePlayer,
    Card,
    Deduction,
    EventTime,
    Goal,
    Lineup,
    Lineups,
    Match,
    Player,
    Substitution,
    TableRow,
)


class TestBasePlayer:
    def test_base_player_str_returns_name(self, ilc_fake):
        player = ilc_fake.base_player()
        assert str(player) == player.name

    def test_equality_ignores_name_if_id_is_non_zero(self, ilc_fake):
        player1 = ilc_fake.base_player()

        # Shorten name by one letter
        player2 = BasePlayer(player_id=player1.player_id, name=player1.name[:-1])

        # Should be equal because ID numbers are equal
        assert player1 == player2
        assert player1 in [player2]

    def test_equality_compares_name_if_id_is_zero(self, ilc_fake):
        player1 = ilc_fake.base_player()
        player1.player_id = 0

        # Shorten name by one letter
        player2 = BasePlayer(player_id=player1.player_id, name=player1.name[:-1])

        # Should be unequal because ID numbers are zero and names don't match
        assert player1 != player2
        assert player1 not in [player2]

    def test_equality_compares_true_if_id_is_zero_and_names_match(self, ilc_fake):
        player1 = ilc_fake.base_player()
        player1.player_id = 0

        # Make identical player
        player2 = BasePlayer(player_id=player1.player_id, name=player1.name)

        # Should be equal because ID numbers are zero and names match
        assert player1 == player2
        assert player1 in [player2]


class TestPlayer:
    def test_player_str_returns_name(self, ilc_fake):
        player = ilc_fake.player()
        assert str(player) == player.name

    def test_dob_rejects_pre_1900(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()
        player_dict["dob"] = "1899-31-12"
        with pytest.raises(ValidationError):
            Player(**player_dict)

    def test_dob_rejects_date_time_format(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()
        player_dict["dob"] = "2025-03-25T20:49:21"
        with pytest.raises(ValidationError):
            Player(**player_dict)

    def test_dob_accepts_empty_string(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()

        # Set to empty string
        player_dict["dob"] = ""
        assert Player(**player_dict).dob == ""

    def test_dob_accepts_missing_zeros(self, ilc_fake):
        player = ilc_fake.player()
        player_dict = player.model_dump()

        # Set to empty string
        player_dict["dob"] = "2000-9-7"
        assert Player(**player_dict).dob == "2000-09-07"


class TestLineup:
    def test_empty_lineup_is_falsy(self):
        assert not Lineup()

    def test_populated_lineup_is_truthy(self, ilc_fake):
        lineup = ilc_fake.lineup()
        assert lineup

    def test_sort_leaves_starting_goalkeeper_first(self, ilc_fake):
        lineup = ilc_fake.lineup()
        starting_keeper = lineup.starting[0][0]
        lineup.sort()
        assert lineup.starting[0][0] == starting_keeper

    def test_sort_order(self, ilc_fake):
        lineup = ilc_fake.lineup()
        lineup.sort()
        starting = [p[0] for p in lineup.starting[1:]]
        subs = [p[0] for p in lineup.subs]
        assert starting == sorted(starting)
        assert subs == sorted(subs)

    def test_sort_empty_lineup_does_nothing(self):
        lineup = Lineup()
        assert not lineup.sort()

    def test_players(self, ilc_fake):
        lineup = ilc_fake.lineup()
        players = lineup.players()
        assert len(players) == 18

    def test_shirt_numbers_are_unique(self, ilc_fake):
        lineup = ilc_fake.lineup()
        shirt_numbers = [p[0] for p in lineup.starting] + [p[0] for p in lineup.subs]
        assert len(shirt_numbers) == len((set(shirt_numbers)))

    def test_len(self, ilc_fake):
        lineup = ilc_fake.lineup()
        assert len(lineup) == len(lineup.starting) + len(lineup.subs)


class TestLineups:
    def test_empty_lineups_is_falsy(self):
        assert not Lineups()

    def test_populated_lineups_is_truthy(self, ilc_fake):
        lineups = ilc_fake.lineups()
        assert lineups

    def test_sort_order(self, ilc_fake):
        lineups = ilc_fake.lineups()
        lineups.sort()
        starting = [p[0] for p in lineups.home.starting[1:]]
        subs = [p[0] for p in lineups.home.subs]
        assert starting == sorted(starting)
        assert subs == sorted(subs)
        starting = [p[0] for p in lineups.away.starting[1:]]
        subs = [p[0] for p in lineups.away.subs]
        assert starting == sorted(starting)
        assert subs == sorted(subs)

    def test_len(self, ilc_fake):
        lineups = ilc_fake.lineups()
        assert len(lineups) == len(lineups.home) + len(lineups.away)


class TestEvents:
    def test_event_time_raises_error(self):
        with pytest.raises(ValueError):
            EventTime(minutes=60, plus=5)

    def test_event_time_str_without_plus_time(self, ilc_fake):
        t = EventTime(minutes=37)
        assert str(t) == "37'"

    def test_event_time_str_with_plus_time(self, ilc_fake):
        t = EventTime(minutes=90, plus=3)
        assert str(t) == "90+3'"

    def test_goal_returns_player(self, ilc_fake):
        player = ilc_fake.base_player()
        goal = Goal(
            team=ilc_fake.team_name(), time=ilc_fake.event_time(), scorer=player
        )
        assert goal.players() == [player]

    def test_card_returns_player(self, ilc_fake):
        player = ilc_fake.base_player()
        card = Card(
            team=ilc_fake.team_name(),
            time=ilc_fake.event_time(),
            player=player,
            color="Y",
        )
        assert card.players() == [player]

    def test_sub_returns_players(self, ilc_fake):
        player_on = ilc_fake.base_player()
        player_off = ilc_fake.base_player()
        sub = Substitution(
            team=ilc_fake.team_name(),
            time=ilc_fake.event_time(),
            player_on=player_on,
            player_off=player_off,
        )
        assert all(p in sub.players() for p in (player_on, player_off))

    def test_event_str_without_plus_time(self, ilc_fake):
        event = Goal(
            team=ilc_fake.team_name(),
            time=EventTime(minutes=37),
            scorer=ilc_fake.player(),
        )
        assert event.time_str() == "37'"

    def test_event_str_with_plus_time(self, ilc_fake):
        event = Goal(
            team=ilc_fake.team_name(),
            time=EventTime(minutes=90, plus=3),
            scorer=ilc_fake.player(),
        )
        assert event.time_str() == "90+3'"

    def test_event_str_returns_players(self, ilc_fake):
        player = ilc_fake.player()
        event = Goal(
            team=ilc_fake.team_name(), time=EventTime(minutes=37), scorer=player
        )
        assert event.players() == [player]


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

    def test_involves(self, ilc_fake):
        home = ilc_fake.team()
        away = ilc_fake.team()
        other = ilc_fake.team()
        match = ilc_fake.match(home=home, away=away)
        assert match.involves(home.name)
        assert match.involves(away.name)
        assert not match.involves(other.name)

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
            assert event in match.events()
            match.delete_event(event)
            assert event not in match.events()

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

    def test_str_gives_score(self, ilc_fake):
        match = ilc_fake.match()
        assert " - ".join((str(match.score.home), str(match.score.away))) in str(match)

    def test_str_unplayed_gives_vs(self, ilc_fake):
        match = ilc_fake.match(status="NS")
        assert " vs " in str(match)


class TestTableRow:
    def test_tuple_calculates_played(self, ilc_fake):
        row = ilc_fake.table_row().as_tuple()
        assert row[1] == sum(row[n] for n in range(2, 5))

    def test_tuple_calculates_gd(self, ilc_fake):
        row = ilc_fake.table_row().as_tuple()
        assert row[7] == row[5] - row[6]

    def test_tuple_calculates_points(self, ilc_fake):
        row = ilc_fake.table_row().as_tuple()
        assert row[8] == row[2] * 3 + row[3]

    def test_handles_deduction(self, ilc_fake):
        row = ilc_fake.table_row()
        points = row.points
        row.deducted = 10
        assert row.points == points - 10

    def test_str(self, ilc_fake):
        row = ilc_fake.table_row()
        assert f"Pts{row.points}" in str(row)

    def test_sort(self, ilc_fake):
        rows = [ilc_fake.table_row() for _ in range(10)]
        rows.sort(reverse=True)
        previous = None
        for row in rows:  # pragma: no cover
            if previous:
                if row.points == previous.points:
                    if row.gd == previous.gd:
                        if row.scored == previous.scored:
                            assert row.team < previous.team
                        else:
                            assert row.scored < previous.scored
                    else:
                        assert row.gd < previous.gd
                else:
                    assert row.points < previous.points
            previous = row

    def test_sort_alphabetical(self, ilc_fake):
        row = ilc_fake.table_row()
        row2 = TableRow.from_tuple(row.as_tuple())
        row.team = "aaaaa"
        row2.team = "zzzzz"
        assert sorted((row, row2), reverse=True) == [row, row2]
        assert sorted((row2, row), reverse=True) == [row, row2]

    def test_not_implemented_eq(self, ilc_fake):
        row = ilc_fake.table_row()
        assert row != 4

    def test_from_tuple(self, ilc_fake):
        row = ilc_fake.table_row()
        row2 = TableRow.from_tuple(row.as_tuple())
        assert row == row2


class TestLeague:
    def test_title(self, fake_league):
        title = fake_league.title
        assert fake_league.name in title
        assert str(fake_league.year) in title

    def test_matches_sorted_by_date(self, fake_league):
        matches = fake_league.matches()
        previous = None
        for match in matches:
            if previous is not None:
                assert match.date >= previous.date
            previous = match

    def test_matches_filtered_by_team(self, fake_league):
        team = fake_league.teams[0]
        matches = fake_league.matches(team=team)
        for match in matches:
            assert match.teams.home == team or match.teams.away == team

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
            if event.date == match.date:
                if event.event.event_type == "status":
                    assert event.event.status == "starting"
                    break
        else:  # pragma: no cover
            assert False

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


class TestLeagueTable:
    def test_league_table_is_correct_size(self, fake_league):
        table = fake_league.table()
        assert len(table) == len(fake_league.teams)

    def test_all_teams_have_played_the_same_number_of_matches(self, fake_league):
        table = fake_league.table()
        played = table[0][1]
        assert all(row[1] == played for row in table)

    def test_all_teams_are_in_the_league_table(self, fake_league):
        table = fake_league.table()
        assert all(row[0] in fake_league.teams for row in table)

    def test_table_is_correctly_ordered(self, fake_league):
        table = fake_league.table()
        # Skip mid-point if there is a league split
        skip = (len(table) // 2) if fake_league.split else 0
        for n in range(1, len(table)):  # pragma: no cover
            if n != skip:
                previous = table[n - 1]
                row = table[n]
                assert row[8] <= previous[8]
                if row[8] == previous[8]:
                    assert row[7] <= previous[7]
                    if row[7] == previous[7]:
                        assert row[5] <= previous[5]
                        if row[5] == previous[5]:
                            assert row[0] >= previous[0]

    def test_table_on_date(self, fake_league):
        # Find out how many matches are played on the opening day
        matches = fake_league.matches()
        date = matches[0].date
        matches_on_date = sum(1 for match in matches if match.date == date)

        # Get the league table on that date
        # Total of 'played' column should be twice the number of matches played
        table = fake_league.table(date=date)
        played = sum(row[1] for row in table)
        assert played == matches_on_date * 2

    def test_table_with_matches_played(self, fake_league):
        table = fake_league.table(played=10)
        assert all(row[1] >= 10 for row in table)

    def test_table_at_split(self, ilc_fake):
        league = ilc_fake.league(
            team_count=6, games_per_opponent=4, split_mode="fixed", games_before_split=3
        )
        table = league.table(split_point=True)
        assert all(row[1] == 15 for row in table)

    def test_handles_deduction(self, ilc_fake):
        league = ilc_fake.league(team_count=6)
        table = league.table()
        team = table[0][0]
        points = table[0][-1]

        league.deductions = [Deduction(team=team, points=10)]
        table = league.table()
        for row in table:
            if row[0] == team:
                assert row[-1] == points - 10
                break

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
            if row[0] == team:
                pre_points = row[-1]
                break

        # Get points the day after the deduction
        table = league.table(date=post_date)
        post_points = 0
        for row in table:
            if row[0] == team:
                post_points = row[-1]
                break

        # There should be a reduction in points
        assert post_points < pre_points

    def test_deduction_accepts_empty_string_for_date(self):
        d = Deduction(team="Team", points=10, date="")
        assert not d.date

    def test_deduction_rejects_invalid_format(self):
        with pytest.raises(ValidationError):
            Deduction(
                team="Team",
                points=10,
                date="10/10/2025",
            )
