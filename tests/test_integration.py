"""Reads against the real Factorial API with FACTORIAL_EMAIL / FACTORIAL_PASSWORD. Writes nothing."""

import datetime as dt
import os
import unittest

import factorial_time_tracking as f


class FactorialApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = f.Client()
        cls.client.login(os.environ["FACTORIAL_EMAIL"], os.environ["FACTORIAL_PASSWORD"])

    def test_reads_have_the_fields_the_cli_relies_on(self):
        today = dt.date.today()
        periods = self.client.periods(today.year, today.month)
        self.assertEqual(len(periods), 1)
        period = periods[0]
        self.assertEqual(sorted(k for k in ("id", "employee_id", "start_on", "end_on") if k in period), ["employee_id", "end_on", "id", "start_on"])

        calendar = self.client.calendar(period["employee_id"], today.year, today.month)
        self.assertEqual(len(calendar), (dt.date.fromisoformat(period["end_on"]) - dt.date.fromisoformat(period["start_on"])).days + 1)
        self.assertEqual({k: type(calendar[0][k]) for k in ("date", "is_laborable_by_contract", "leaves")},
                         {"date": str, "is_laborable_by_contract": bool, "leaves": list})

        shifts = self.client.shifts(period["employee_id"], today.year, today.month)
        self.assertEqual({s["date"][:7] for s in shifts} - {f"{today:%Y-%m}"}, set())

    def test_wrong_credentials_fail_with_auth_exit_code(self):
        with self.assertRaises(f.FactorialError) as ctx:
            f.Client().login("nobody@example.invalid", "wrong-password")
        self.assertEqual(ctx.exception.exit_code, f.EXIT_AUTH)
        self.assertIn("FACTORIAL_EMAIL and FACTORIAL_PASSWORD", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
