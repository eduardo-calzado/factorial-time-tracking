import datetime as dt
import json
import pathlib
import unittest

import factorial_time_tracking as f

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
FULL_DAY = [("09:00", "14:00"), ("15:00", "18:00")]


def load(name):
    return json.loads((FIXTURES / name).read_text())


def plan_month(calendar, today, shift_counts=None):
    shift_counts = shift_counts or {}
    return {d["date"]: f.plan_day(d, shift_counts.get(d["date"], 0), today) for d in calendar}


class PlanDayTest(unittest.TestCase):
    def test_july_has_one_absence_and_one_regional_holiday(self):
        plan = plan_month(load("calendar_2026_07.json"), dt.date(2026, 11, 26))
        want = {
            "2026-07-15": (FULL_DAY, None),
            "2026-07-16": ([], "absence"),
            "2026-07-18": ([], "not a working day"),
            "2026-07-19": ([], "not a working day"),
            "2026-07-28": ([], "holiday: Día de las Instituciones (Cantabria)"),
        }
        self.assertEqual({k: plan[k] for k in want}, want)
        self.assertEqual(sum(1 for shifts, _ in plan.values() if shifts), 21)

    def test_september_holiday_inside_absence_reports_the_holiday(self):
        plan = plan_month(load("calendar_2026_09.json"), dt.date(2026, 11, 26))
        want = {
            "2026-09-11": (FULL_DAY, None),
            "2026-09-14": ([], "absence"),
            "2026-09-15": ([], "holiday: Festividad de la Bien Aparecida"),
            "2026-09-30": ([], "absence"),
        }
        self.assertEqual({k: plan[k] for k in want}, want)

    def test_cases(self):
        workday = {"date": "2026-07-15", "is_laborable": False, "is_laborable_by_contract": True, "leaves": []}
        half_day_leave = {"type": "leave", "is_workable": False, "half_day": "beginning_of_day", "day_type": "half"}
        workable_leave = {"type": "leave", "is_workable": True, "half_day": None, "day_type": "full"}
        cases = [
            ("workday", workday, 0, dt.date(2026, 11, 26), (FULL_DAY, None)),
            ("today counts", workday, 0, dt.date(2026, 7, 15), (FULL_DAY, None)),
            ("future", workday, 0, dt.date(2026, 7, 14), ([], "future")),
            ("existing shifts", workday, 1, dt.date(2026, 11, 26), ([], "already has 1 shift(s)")),
            ("half-day absence", {**workday, "leaves": [half_day_leave]}, 0, dt.date(2026, 11, 26),
             ([], "WARN partial absence, fill this day by hand")),
            ("workable leave", {**workday, "leaves": [workable_leave]}, 0, dt.date(2026, 11, 26), (FULL_DAY, None)),
        ]
        for name, day, shift_count, today, want in cases:
            with self.subTest(name):
                self.assertEqual(f.plan_day(day, shift_count, today), want)

    def test_custom_shifts(self):
        workday = {"date": "2026-07-15", "is_laborable": False, "is_laborable_by_contract": True, "leaves": []}
        self.assertEqual(f.plan_day(workday, 0, dt.date(2026, 11, 26), [("08:00", "15:00")]), ([("08:00", "15:00")], None))


class ParseShiftsTest(unittest.TestCase):
    def test_valid(self):
        cases = [
            ("default", "09:00-14:00,15:00-18:00", FULL_DAY),
            ("one shift", "08:00-15:00", [("08:00", "15:00")]),
            ("spaces", " 08:00 - 15:00 ", [("08:00", "15:00")]),
            ("back to back", "09:00-13:00,13:00-17:00", [("09:00", "13:00"), ("13:00", "17:00")]),
        ]
        for name, text, want in cases:
            with self.subTest(name):
                self.assertEqual(f.parse_shifts(text), want)

    def test_invalid(self):
        cases = [
            ("not a range", "09:00"),
            ("not a time", "nine-five"),
            ("ends before it starts", "14:00-09:00"),
            ("empty shift", "09:00-09:00"),
            ("overlap", "09:00-14:00,13:00-18:00"),
            ("out of order", "15:00-18:00,09:00-14:00"),
        ]
        for name, text in cases:
            with self.subTest(name), self.assertRaises(f.argparse.ArgumentTypeError):
                f.parse_shifts(text)


class MonthsBetweenTest(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("same month", dt.date(2026, 6, 1), dt.date(2026, 6, 30), [(2026, 6)]),
            ("across year", dt.date(2026, 11, 30), dt.date(2027, 2, 1), [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]),
        ]
        for name, start, end, want in cases:
            with self.subTest(name):
                self.assertEqual(list(f.months_between(start, end)), want)


if __name__ == "__main__":
    unittest.main()
