"""Runs the CLI as a process against the real Factorial account. Dry runs only: the --apply path is checked by hand (see README)."""

import os
import pathlib
import subprocess
import sys
import unittest

CLI = pathlib.Path(__file__).parent.parent / "skills" / "factorial-time-tracking" / "scripts" / "factorial_time_tracking.py"
# Already filled by the June-November 2026 backfill, so a dry run must plan nothing.
FILLED_RANGE = ["--from", "2026-06-01", "--to", "2026-11-26"]


def run_cli(args, env):
    return subprocess.run([sys.executable, str(CLI), *args], env=env, capture_output=True, text=True, timeout=300)


class CliTest(unittest.TestCase):
    def test_dry_run_over_filled_range_plans_nothing(self):
        res = run_cli(FILLED_RANGE, os.environ)
        self.assertEqual((res.returncode, res.stderr), (0, ""))
        lines = res.stdout.splitlines()
        self.assertEqual(lines[-1], "would create 0 shift(s); 0 day(s) to fill by hand (dry run, pass --apply to write)")
        self.assertIn("2026-07-28 Tue  skip  holiday: Día de las Instituciones (Cantabria)", lines)
        self.assertIn("2026-06-01 Mon  skip  already has 2 shift(s)", lines)

    def test_custom_shifts_over_filled_range_plans_nothing(self):
        res = run_cli([*FILLED_RANGE, "--shifts", "08:00-15:00"], os.environ)
        self.assertEqual((res.returncode, res.stderr), (0, ""))
        self.assertEqual(res.stdout.splitlines()[-1], "would create 0 shift(s); 0 day(s) to fill by hand (dry run, pass --apply to write)")

    def test_bad_shifts_exit_2_before_login(self):
        res = run_cli(["--shifts", "14:00-09:00"], {})
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertIn("argument --shifts: bad shift '14:00-09:00'", res.stderr)

    def test_missing_credentials_exit_2_with_help(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("FACTORIAL_")}
        res = run_cli([], env)
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertIn("FACTORIAL_EMAIL and FACTORIAL_PASSWORD must be set", res.stderr)

    def test_wrong_credentials_exit_2(self):
        env = {**os.environ, "FACTORIAL_EMAIL": "nobody@example.invalid", "FACTORIAL_PASSWORD": "wrong-password"}
        res = run_cli([], env)
        self.assertEqual((res.returncode, res.stdout), (2, ""))
        self.assertIn("Factorial login failed", res.stderr)


if __name__ == "__main__":
    unittest.main()
