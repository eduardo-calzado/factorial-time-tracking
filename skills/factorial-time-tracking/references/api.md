# Factorial internal API notes

Factorial's public API needs an admin-issued key. Employees without one can use the same internal API the web app
(`app.factorialhr.com`) calls, authenticated with the session cookies of a normal login. None of this is documented or
versioned by Factorial: it was found by watching the web app's requests and reading its JS bundles, and confirmed against
a real account in November 2026. Expect it to change.

## Hosts

From `https://app.factorialhr.com/environment.json` (public):

| Key | Value |
|---|---|
| `api_endpoint` | `https://api.factorialhr.com` |
| `factorial_id_endpoint` | `https://id.factorialhr.com` |

**Cloudflare** sits in front of both and answers `403` to the default `Python-urllib/x` user agent. Any other user
agent (curl's, or a custom one such as `factorial-time-tracking/1.0`) gets through.

## Authentication

### Email and password (what the CLI uses)

```
POST https://id.factorialhr.com/api/auth/challenges/first_factor
Content-Type: application/json

{"email": "...", "password": "..."}
```

- `200 {"success": true, "next": {"type": "redirect", "to": "https://app.factorialhr.com"}}` plus `Set-Cookie`
  `_factorial_id`, `_factorial_id_data`, `_factorial_id_refresh`. Send those cookies to `api.factorialhr.com`.
- `422 {"success": false, "error": {"code": "invalid_credentials"}, "next": {"available_methods": [...]}}` for wrong
  credentials.
- If the account needs a second factor or forces SSO, `next` is something other than `redirect`. Not handled.

Only works when the account has a Factorial password. A Google/Microsoft SSO-only account has none.

### Session lifetime and refresh

- `_factorial_id` is a JWT valid for **15 minutes** (`exp - iat = 900`).
- The web app renews it with `POST https://id.factorialhr.com/api/auth/refresh` (cookies only, no body), which
  **rotates** `_factorial_id_refresh`: the previous refresh token stops working. Two clients sharing one session (a
  browser tab and a script with a copied cookie) invalidate each other; the loser gets
  `401 {"error": {"code": "invalid_refresh_token"}}`.
- That is why the CLI logs in with email and password on every run instead of storing a cookie.

## Attendance endpoints

All on `https://api.factorialhr.com`, JSON, authenticated by the cookies above. An expired session answers `401`.

### Periods: one per employee and month

```
GET /attendance/periods?year=2026&month=11
```

Returns a list with the caller's period: `id`, `employee_id`, `year`, `month`, `start_on`, `end_on`, `state`,
`worked_minutes`, ... Every shift belongs to a `period_id`. This is also the simplest way to learn your own
`employee_id`.

### Shifts

```
GET /attendance/shifts?employee_id=<id>&year=2026&month=11
```

- `year` + `month` filter correctly. `start_on`/`end_on` are **ignored** (you get every shift since you joined), and
  `period_id` alone is rejected with `400 Invalid parameters`.
- Fields used: `id`, `date`, `clock_in`/`clock_out` (`"HH:MM"`), `minutes`, `period_id`, `workable`.

```
POST /attendance/shifts
{"period_id": 123, "clock_in": "09:00", "clock_out": "14:00", "minutes": 0, "date": "2026-06-01", "day": 1,
 "observations": null, "history": []}
```

Factorial computes `minutes` itself (the created shift above comes back with `300`). One request per shift: two
shifts a day means two requests.

```
DELETE /attendance/shifts/<id>
```

### Calendar: working days, holidays and absences

```
GET /attendance/calendar?id=<employee_id>&year=2026&month=12
```

One row per day of the month:

```json
{"date": "2026-12-08", "day": 8, "is_laborable": false, "is_laborable_by_contract": true, "is_leave": true,
 "leaves": [{"type": "bank_holiday", "name": "Día de la Inmaculada Concepción", "day_type": "full",
             "half_day": null, "is_workable": false}]}
```

- **Use `is_laborable_by_contract`**, not `is_laborable`. On the account this was built against, `is_laborable` was
  `false` for every day, including normal Tuesdays, while `is_laborable_by_contract` was `false` exactly on weekends.
- `leaves[].type` is `bank_holiday` (public holiday of the employee's calendar) or `leave` (an absence).
- Only **approved** absences appear: an unapproved one existed in `/leaves` and was missing from the calendar.
- `half_day` / `day_type` mark partial absences; `is_workable: true` marks leave types that still count as work.

### Absences with their approval state

```
GET /leaves?employee_id=<id>
```

Each item has `start_on`, `finish_on`, `approved`, `half_day`, `hourly`, `leave_type_id`. Not used by the CLI, since the
calendar already filters to approved absences.

## Other things seen in the web app

- Most of the web app now talks GraphQL at `POST https://api.factorialhr.com/graphql?<OperationName>`, but the
  attendance pages above still use the REST endpoints.
- The "My time tracking" page is `https://app.factorialhr.com/attendance/clock-in/monthly/<year>/<month>/1`.

## Prior art

[DanielRamosAcosta/factorial-cli](https://github.com/DanielRamosAcosta/factorial-cli) (TypeScript, MIT) uses the same
login and shift endpoints. It decides working days with `is_laborable` (which can be `false` everywhere, see above) and
has no dry-run, which is why this tool exists.
