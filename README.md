# factorial-time-tracking

Fills your [Factorial](https://factorialhr.com) time tracking with a fixed schedule, **09:00-14:00 and 15:00-18:00**,
on every working day. It skips:

- weekends and any day your contract marks as non-working;
- public holidays from your Factorial calendar;
- approved absences (vacations, sick leave, ...);
- days that already have shifts, so it is safe to run again and again;
- future days.

Days with a half-day absence are skipped and flagged `WARN ... fill this day by hand`.

It needs no admin API key: it logs in with your own email and password and uses the same internal API as the web app.
How that API works is in [skills/factorial-time-tracking/references/api.md](skills/factorial-time-tracking/references/api.md).

## Requirements

- Python 3.10+ (standard library only, no `pip install`).
- A Factorial account **with a password**. Accounts that only sign in with Google/Microsoft SSO or need 2FA are not
  supported.
- For the scheduled run: Linux with systemd (installed for you), or any machine with cron.

## Install

Everything the tool needs lives in [`skills/factorial-time-tracking/`](skills/factorial-time-tracking/), which is also the agent skill (see [Agent plugin](#agent-plugin-claude-code-codex)),
so installing the plugin ships the CLI too. `install.sh` is idempotent. It copies the CLI to `~/.local/bin/factorial-time-tracking` and enables a systemd user timer that runs
every **Friday at 17:00**.

### Automatic (recommended)

With `npx` (Node 22+). The first line installs the skill, with the CLI inside, for Claude Code, Codex and other agents;
the second puts the CLI on PATH and enables the Friday timer:

```bash
npx skills add eduardo-calzado/factorial-time-tracking -g
~/.agents/skills/factorial-time-tracking/scripts/install.sh
```

### Manual

With `curl` (only git, Python and systemd). It clones the repo into `~/projects/factorial-time-tracking`, or updates it,
and runs the same installer:

```bash
curl -fsSL https://raw.githubusercontent.com/eduardo-calzado/factorial-time-tracking/main/install.sh | bash
```

### Configuration

Put your credentials in `~/.config/secrets.env` (`chmod 600`), which the timer sources:

```bash
export FACTORIAL_EMAIL='you@company.com'
export FACTORIAL_PASSWORD='...'
```

Want a different schedule? Edit `SHIFTS` at the top of `skills/factorial-time-tracking/scripts/factorial_time_tracking.py` and re-run `install.sh`
(the timer runs the installed copy).

## Two ways to run it

1. **Scheduled, the recommended way.** A weekly job fills the last two weeks every Friday, so you never think about it.
   `install.sh` sets it up as a systemd timer (see [The weekly timer](#the-weekly-timer)); without systemd, use
   [cron](#cron-instead-of-systemd). Days already filled are skipped, so the overlapping window is harmless and catches up a
   week the machine was off.
2. **Backfill, when you need it.** Fill any past range at once with `--from`/`--to`, for example when you start using the
   tool or after a gap. Always look at the dry run first, then repeat it with `--apply`. Running it again is safe.

## Usage

```bash
set -a; . ~/.config/secrets.env; set +a

factorial-time-tracking                                   # dry run for this week (Monday to today)
factorial-time-tracking --apply                           # create this week's shifts
factorial-time-tracking --from 2026-06-01                 # dry run of a backfill
factorial-time-tracking --from 2026-06-01 --apply         # backfill
factorial-time-tracking --from 2026-06-01 --to 2026-06-01 --apply   # a single day
```

Output, one line per day:

```
2026-07-15 Wed  would create  09:00-14:00, 15:00-18:00
2026-07-16 Thu  skip  absence
2026-07-28 Tue  skip  holiday: Día de las Instituciones (Cantabria)
would create 42 shift(s); 0 day(s) to fill by hand (dry run, pass --apply to write)
```

Exit codes: `0` success, `1` API or network error, `2` login failed or credentials missing. The error message says what
to fix.

## The weekly timer

`skills/factorial-time-tracking/scripts/systemd/factorial-time-tracking.service` runs `factorial-time-tracking --apply --from <14 days ago>`. The two-week window catches up a
Friday the machine was off (`Persistent=true` also runs a missed timer at the next boot).

```bash
systemctl --user list-timers factorial-time-tracking.timer      # next run
systemctl --user start factorial-time-tracking.service          # run it now
systemctl --user status factorial-time-tracking.service         # "failed" if the last run failed
journalctl --user -u factorial-time-tracking.service -n 50      # what it did
```

A failed run leaves the unit `failed`: the CLI never exits `0` after an error.

### Cron instead of systemd

On macOS or a machine without systemd, copy the CLI and add a crontab line (`crontab -e`). `%` must be escaped in crontab,
and missed runs are not caught up by cron itself, only by the next run's two-week window.

```bash
install -m 755 skills/factorial-time-tracking/scripts/factorial_time_tracking.py ~/.local/bin/factorial-time-tracking
```

```crontab
# Linux (GNU date)
0 17 * * 5 . "$HOME/.config/secrets.env" && "$HOME/.local/bin/factorial-time-tracking" --apply --from "$(date -d '-14 days' +\%F)" >>"$HOME/.local/state/factorial-time-tracking.log" 2>&1
# macOS (BSD date)
0 17 * * 5 . "$HOME/.config/secrets.env" && "$HOME/.local/bin/factorial-time-tracking" --apply --from "$(date -v-14d +\%F)" >>"$HOME/.local/state/factorial-time-tracking.log" 2>&1
```

Create `~/.local/state` first. Check the log after a Friday: cron won't tell you a run failed.

If a run dies halfway through a day (first shift created, second not), the next run sees the day as already filled and
skips it. Check the day named in the error on the web.

## Tests

The tests talk to the real Factorial with your credentials. Nothing is mocked.

```bash
cd ~/projects/factorial-time-tracking
set -a; . ~/.config/secrets.env; set +a
python3 -m unittest discover -s tests -t . -v
```

- `tests/test_unit.py`: the day-by-day decision, against real calendar responses saved in `tests/fixtures/` (absence
  names replaced by `Absence`).
- `tests/test_integration.py`: login and the read endpoints the CLI relies on. Read-only.
- `tests/test_e2e.py`: the CLI as a process, using dry runs only. It asserts on dates of the author's account (June to
  November 2026 is already filled), so change `FILLED_RANGE` and the expected lines for yours.

`--apply` has no automated test, on purpose, because it writes to your real account. Check it by hand: run a single day
with `--apply`, look at it on the web, and run it again to see `skip  already has 2 shift(s)`.

## Agent plugin (Claude Code, Codex)

This repo is also a plugin marketplace with one plugin, `factorial-time-tracking`. Its skill
(`skills/factorial-time-tracking/SKILL.md`) teaches the agent to run and fix this tool: dry run first, `--apply` only on
request, how to read the timer, and what each error means. The CLI ships inside the skill: the agent can run it from there, or (with your OK) run the skill's `scripts/install.sh` to
put it on PATH and enable the timer. After a plugin update, re-run `install.sh` so the installed copy matches.

```bash
# Claude Code
claude plugin marketplace add eduardo-calzado/factorial-time-tracking
claude plugin install factorial-time-tracking@factorial-time-tracking

# Codex
codex plugin marketplace add eduardo-calzado/factorial-time-tracking
codex plugin add factorial-time-tracking@factorial-time-tracking
```

Inside a Claude Code session the one-step form is
`/plugin install factorial-time-tracking --marketplace eduardo-calzado/factorial-time-tracking`.

The plugin has no `version`, so each commit is a new version. Pick it up with `claude plugin marketplace update factorial-time-tracking`
plus `claude plugin update factorial-time-tracking@factorial-time-tracking`, or `codex plugin marketplace upgrade`.

Other agents: use the `npx skills add` line from [Install](#install), or link the skill folder into the agent's skills directory.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Factorial login failed` | Wrong or missing `FACTORIAL_EMAIL`/`FACTORIAL_PASSWORD`, or your password changed. Try logging in on the web. |
| `login needs another step (2FA or SSO?)` | Your account requires a second factor or SSO. Not supported. |
| `HTTP 403` with an HTML body | Cloudflare blocked the request. Check that `USER_AGENT` is still set, and whether Factorial changed its bot rules. |
| `HTTP 400 Invalid parameters` | Factorial changed an endpoint. Compare with the web app's requests and update [api.md](skills/factorial-time-tracking/references/api.md). |
