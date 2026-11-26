#!/usr/bin/env python3
"""Fill your Factorial time tracking with a fixed daily schedule.

Uses the internal API behind app.factorialhr.com (see ../references/api.md), logging in with your own email and password.
"""

import argparse
import datetime as dt
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

ID_URL = "https://id.factorialhr.com"
API_URL = "https://api.factorialhr.com"
# Cloudflare in front of Factorial rejects the default "Python-urllib" user agent with a 403.
USER_AGENT = "factorial-time-tracking/1.0"
SHIFTS = [("09:00", "14:00"), ("15:00", "18:00")]

EXIT_ERROR = 1
EXIT_AUTH = 2

AUTH_HELP = (
    "Factorial login failed. Check FACTORIAL_EMAIL and FACTORIAL_PASSWORD "
    "(on the VM they live in ~/.config/secrets.env) and that you can log in with them at https://app.factorialhr.com."
)


class FactorialError(Exception):
    def __init__(self, message, exit_code=EXIT_ERROR):
        super().__init__(message)
        self.exit_code = exit_code


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method, url, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        })
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode(errors="replace")
            if e.code in (401, 403):
                raise FactorialError(f"{method} {url} -> HTTP {e.code}: {detail}\n{AUTH_HELP}", EXIT_AUTH) from e
            raise FactorialError(f"{method} {url} -> HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise FactorialError(f"{method} {url} -> {e.reason}") from e
        return json.loads(raw) if raw else None

    def login(self, email, password):
        try:
            resp = self.request("POST", f"{ID_URL}/api/auth/challenges/first_factor", {"email": email, "password": password})
        except FactorialError as e:
            raise FactorialError(f"{e}\n{AUTH_HELP}", EXIT_AUTH) from e
        if not resp or not resp.get("success"):
            raise FactorialError(f"login rejected: {json.dumps(resp)[:300]}\n{AUTH_HELP}", EXIT_AUTH)
        if resp.get("next", {}).get("type") != "redirect":
            raise FactorialError(f"login needs another step (2FA or SSO?), not supported: {json.dumps(resp.get('next'))[:300]}", EXIT_AUTH)

    def periods(self, year, month):
        return self.request("GET", f"{API_URL}/attendance/periods?year={year}&month={month}")

    def calendar(self, employee_id, year, month):
        return self.request("GET", f"{API_URL}/attendance/calendar?id={employee_id}&year={year}&month={month}")

    def shifts(self, employee_id, year, month):
        return self.request("GET", f"{API_URL}/attendance/shifts?employee_id={employee_id}&year={year}&month={month}")

    def create_shift(self, period_id, date, clock_in, clock_out):
        return self.request("POST", f"{API_URL}/attendance/shifts", {
            "period_id": period_id,
            "clock_in": clock_in,
            "clock_out": clock_out,
            "minutes": 0,
            "date": date.isoformat(),
            "day": date.day,
            "observations": None,
            "history": [],
        })


def plan_day(day, shift_count, today, shifts=SHIFTS):
    """Return (shifts_to_create, reason). A reason starting with WARN marks a day to fill by hand."""
    date = dt.date.fromisoformat(day["date"])
    if date > today:
        return [], "future"
    if not day["is_laborable_by_contract"]:
        return [], "not a working day"
    for leave in day["leaves"]:
        if leave.get("is_workable"):
            continue
        if leave["type"] == "bank_holiday":
            return [], f"holiday: {leave.get('name') or 'bank holiday'}"
        if leave.get("half_day") or leave.get("day_type") not in (None, "full"):
            return [], "WARN partial absence, fill this day by hand"
        return [], "absence"
    if shift_count:
        return [], f"already has {shift_count} shift(s)"
    return list(shifts), None


def parse_shifts(text):
    """Parse "09:00-14:00,15:00-18:00" into [("09:00", "14:00"), ("15:00", "18:00")]."""
    shifts = []
    for part in text.split(","):
        try:
            start, end = (dt.time.fromisoformat(t.strip()) for t in part.split("-"))
        except ValueError:
            raise argparse.ArgumentTypeError(f"bad shift {part!r}, expected HH:MM-HH:MM") from None
        if start >= end or (shifts and start < shifts[-1][1]):
            raise argparse.ArgumentTypeError(f"bad shift {part!r}: shifts must be in order, not overlap, and end after they start")
        shifts.append((start, end))
    return [(f"{a:%H:%M}", f"{b:%H:%M}") for a, b in shifts]


def months_between(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def run(client, start, end, today, apply, shifts=SHIFTS, out=print):
    created = 0
    warnings = 0
    for year, month in months_between(start, end):
        periods = client.periods(year, month)
        if len(periods) != 1:
            raise FactorialError(f"expected one attendance period for {year}-{month:02d}, got {len(periods)}")
        period = periods[0]
        employee_id = period["employee_id"]
        calendar = client.calendar(employee_id, year, month)
        shift_counts = {}
        for shift in client.shifts(employee_id, year, month):
            shift_counts[shift["date"]] = shift_counts.get(shift["date"], 0) + 1
        for day in calendar:
            date = dt.date.fromisoformat(day["date"])
            if not start <= date <= end:
                continue
            planned, reason = plan_day(day, shift_counts.get(day["date"], 0), today, shifts)
            if reason:
                warnings += reason.startswith("WARN")
                out(f"{date} {date:%a}  skip  {reason}")
                continue
            for clock_in, clock_out in planned:
                if apply:
                    client.create_shift(period["id"], date, clock_in, clock_out)
                created += 1
            verb = "created" if apply else "would create"
            out(f"{date} {date:%a}  {verb}  " + ", ".join(f"{a}-{b}" for a, b in planned))
    out(f"{'created' if apply else 'would create'} {created} shift(s); {warnings} day(s) to fill by hand" + ("" if apply else " (dry run, pass --apply to write)"))
    return created


def main(argv=None):
    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    parser = argparse.ArgumentParser(description="Fill Factorial time tracking with a fixed schedule on every working day.")
    parser.add_argument("--from", dest="start", type=dt.date.fromisoformat, default=monday, help="first day, YYYY-MM-DD (default: this Monday)")
    parser.add_argument("--to", dest="end", type=dt.date.fromisoformat, default=today, help="last day, YYYY-MM-DD (default: today)")
    parser.add_argument("--apply", action="store_true", help="create the shifts (default: dry run)")
    parser.add_argument("--shifts", type=parse_shifts, default=SHIFTS,
                        help="shifts for each day, e.g. 08:00-15:00 or 09:00-14:00,15:00-18:00 (default: 09:00-14:00,15:00-18:00)")
    args = parser.parse_args(argv)
    if args.start > args.end:
        parser.error("--from is after --to")

    email = os.environ.get("FACTORIAL_EMAIL")
    password = os.environ.get("FACTORIAL_PASSWORD")
    try:
        if not email or not password:
            raise FactorialError(f"FACTORIAL_EMAIL and FACTORIAL_PASSWORD must be set.\n{AUTH_HELP}", EXIT_AUTH)
        client = Client()
        client.login(email, password)
        run(client, args.start, args.end, today, args.apply, args.shifts)
    except FactorialError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
