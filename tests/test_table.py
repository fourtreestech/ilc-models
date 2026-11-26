"""Tests for league table and deduction models"""

import pytest
from pydantic import ValidationError

from ilc_models import (
    Deduction,
    TableRow,
)


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
                            assert row.team >= previous.team
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

    def test_from_tuple_restores_deduction(self, ilc_fake):
        row = ilc_fake.table_row(matches=10)
        row.deducted = 5
        row2 = TableRow.from_tuple(row.as_tuple())
        assert row2.deducted == 5
        assert row2.points == row.points

    def test_form(self, ilc_fake):
        row = TableRow(team=ilc_fake.team_name())
        for result in ("W", "D", "W", "W", "L"):
            row.add_form(result)
        assert row.form == "WDWWL"

    def test_form_replaces_results(self, ilc_fake):
        row = TableRow(team=ilc_fake.team_name())
        for result in ("W", "D", "W", "W", "L"):
            row.add_form(result)
        assert row.form == "WDWWL"
        row.add_form("D")
        assert row.form == "DWWLD"
        row.add_form("W")
        assert row.form == "WWLDW"
        row.add_form("L")
        assert row.form == "WLDWL"

    def test_as_tuple_populates_form(self, ilc_fake):
        row = ilc_fake.table_row()
        row.form = "WDLLW"
        row2 = row.as_tuple()
        assert row2.form == "WDLLW"

    def test_from_tuple_populates_form(self, ilc_fake):
        row = ilc_fake.table_row()
        row.form = "WDLLW"
        row2 = TableRow.from_tuple(row.as_tuple())
        assert row2.form == "WDLLW"


class TestDeduction:
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

    def test_deduction_rejects_impossible_date(self):
        with pytest.raises(ValidationError):
            Deduction(team="Team", points=10, date="2020-19-39")
