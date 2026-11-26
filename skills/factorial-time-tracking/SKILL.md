---
name: factorial-time-tracking
description: Fill, backfill or check Factorial (factorialhr.com) time tracking (fichajes, jornada, turnos) with the factorial-time-tracking CLI, check its weekly systemd timer, and fix it when Factorial login or its internal API breaks. Use when the user asks to fill/rellenar Factorial, backfill missing days, whether the Factorial timer ran, or why it failed.
---

# Factorial time tracking

Everything the tool needs ships next to this file:

- `scripts/factorial_time_tracking.py`: the CLI (Python 3.10+, stdlib only).
- `scripts/install.sh`: copies the CLI to `~/.local/bin/factorial-time-tracking` and enables the Friday systemd timer.
- `scripts/systemd/`: the timer and service units.
- `references/api.md`: Factorial's internal API. Read it before changing the CLI.

## What it does

The CLI creates the shifts in `SHIFTS` (default 09:00-14:00 and 15:00-18:00, or `--shifts` for one run) on every working day in a date range. It skips non-contract days (weekends),
`bank_holiday`s, approved absences, days that already have shifts, and future days. A half-day absence is skipped with
`WARN ... fill this day by hand`: report every WARN line to the user.

It logs in on every run with `FACTORIAL_EMAIL` / `FACTORIAL_PASSWORD`, kept in `~/.config/secrets.env`. It does not use
browser cookies: the session JWT lasts 15 minutes and the refresh token rotates, so a copied cookie dies and also logs the
browser out.

## Setup

If `factorial-time-tracking` is not on PATH, either run the script directly (`python3 <this skill's dir>/scripts/factorial_time_tracking.py`,
same flags) or, with the user's OK, run `<this skill's dir>/scripts/install.sh` (Linux with systemd; it enables a timer that
writes to Factorial every Friday). After the skill is updated, re-run `install.sh` so the installed copy matches. If the credentials are missing, ask the user to add them to
`~/.config/secrets.env` (`chmod 600`); never write or ask for the password in the chat.

## Running it

Agent shells usually don't have the credentials loaded, so source them in the same command:

```bash
set -a; . ~/.config/secrets.env; set +a
factorial-time-tracking                                # dry run, this week (Monday to today)
factorial-time-tracking --from 2026-06-01             # dry run of a backfill
factorial-time-tracking --from 2026-06-01 --apply     # write
factorial-time-tracking --from D --to D --apply       # one day
factorial-time-tracking --shifts 08:00-15:00          # other hours (comma separate several shifts: 09:00-13:00,14:00-17:00)
```

- Always do the dry run first and show the user the summary (days to create, skipped holidays and absences, WARNs). Run
  `--apply` only when the user asked for the write.
- `--apply` writes to the user's real Factorial account. To undo a shift: `DELETE https://api.factorialhr.com/attendance/shifts/<id>`
  (see `references/api.md`), only when the user asks.
- Never print `FACTORIAL_PASSWORD`, session cookies, or raw Factorial responses with personal data.
- Exit codes: `0` ok, `1` API/network error, `2` login failed or credentials missing.

## The weekly timer

`factorial-time-tracking.timer` runs `--apply --from <14 days ago>` every Friday at 17:00 (systemd user unit, `Persistent=true`).

```bash
systemctl --user list-timers factorial-time-tracking.timer
systemctl --user status factorial-time-tracking.service      # "failed" = last run failed
journalctl --user -u factorial-time-tracking.service -n 50 -o cat
```

Machines without systemd use a crontab line instead (README, "Cron instead of systemd"); its output goes to
`~/.local/state/factorial-time-tracking.log`. Prefer the scheduled run for normal weeks; use `--from`/`--to` only to backfill.

The CLI never exits `0` after an error, so a `failed` unit is real and a successful one really filled (or found nothing
to fill). Read the journal for the per-day lines.

## When it breaks

| Symptom | What to do |
|---|---|
| exit 2, `Factorial login failed` | Password changed or missing from `secrets.env`. Ask the user to update it; never write it yourself. |
| `login needs another step (2FA or SSO?)` | The account now needs 2FA/SSO. Email+password no longer works: tell the user, don't work around it. |
| `HTTP 403` with HTML | Cloudflare. `USER_AGENT` must not be the default `Python-urllib`. |
| `HTTP 400 Invalid parameters` / missing fields | Factorial changed the API. Capture the web app's requests on `https://app.factorialhr.com/attendance/clock-in/monthly/<y>/<m>/1` with a headless browser (e.g. Playwright) logged in through the same email+password login, then update the CLI and `references/api.md`. Do not reuse the user's browser cookie. |
| Day half-filled after an error | The next run skips it (it already has shifts). Point the user to the day named in the error. |

## Changing the repo

- Tests live in the repo (not in the installed skill) and hit real Factorial, nothing mocked: `set -a; . ~/.config/secrets.env; set +a && python3 -m unittest discover -s tests -t . -v`
  from the repo root. All must pass with clean output. `--apply` has no automated test: verify a single day by hand with the user.
- Keep employee/company IDs, names and emails out of the repo. Fixtures replace absence names with `Absence`.
- Re-run `scripts/install.sh` after any change: the timer runs the installed copy, not this file.
