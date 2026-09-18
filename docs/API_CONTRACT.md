# API Contract (backend ⇄ frontend)

Source of truth for both sides. The spec (`ktf_2026_draw_spec.md`) defines the product;
this file pins down the exact JSON shapes so backend and frontend can be built in parallel.
If something is ambiguous here, the spec wins; if the spec is silent, this file wins.

## Conventions

- Prefix `/api`, JSON everywhere. WebSocket at `/ws/live`.
- **Timestamps in REST resources** (`created_at`, `started_at`, ...) are ISO-8601 strings with
  timezone, UTC (`2026-09-18T10:15:30.123456+00:00`).
- **Live snapshot** (`/api/live/current`, WS `state` event) uses **epoch milliseconds** for
  `server_time` and `draw.started_at` (as in the spec example) — the client uses them for
  animation timing.
- UUIDs as strings. Enums as upper-case strings.
- Errors: HTTP status + body

  ```json
  { "error": { "code": "STRING_CODE", "message": "Human readable", "details": {} } }
  ```

  `details` is optional. Validation errors: `422`, code `VALIDATION_ERROR`,
  `details.fields = { "<field>": "<message>" }`.
  Unauthenticated admin calls: `401 UNAUTHORIZED`. Unknown route: `404 NOT_FOUND`.
  Common codes are listed per endpoint below.
- Admin session cookie: name `admin_session`, `httpOnly`, `SameSite=Strict`, `Path=/`,
  12 h, `Secure` when `COOKIE_SECURE=true` (default: true iff `PUBLIC_BASE_URL` starts with `https`).
- CSRF: for mutating admin requests (`POST/PUT/PATCH/DELETE`) backend checks that the `Origin`
  header, when present, has the same host as the `Host` header or equals `PUBLIC_BASE_URL` origin
  (or an entry of `ALLOWED_ORIGINS`, comma separated, used for local dev `http://localhost:3000`).
  Mismatch → `403 CSRF_ORIGIN_MISMATCH`.
- CORS (dev only): when `ALLOWED_ORIGINS` is non-empty, backend enables CORS for those origins
  with credentials. In production everything is same-origin through nginx, `ALLOWED_ORIGINS` empty.
- Frontend base URL: `NEXT_PUBLIC_API_BASE` (empty string in production ⇒ relative `/api`;
  `http://localhost:8000` in dev). WS URL derived from it (`ws://localhost:8000/ws/live` in dev,
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/live` in prod).
- Draw screen key: if env `DRAW_SCREEN_KEY` is non-empty, `GET /api/live/current` and
  `WS /ws/live` require query `?key=<DRAW_SCREEN_KEY>` **or** a valid admin session
  (admin dashboard also subscribes). Wrong/missing key → `403 DRAW_KEY_REQUIRED`
  (WS: close with code 4403). The `/draw` page passes through its own `?key=` query param.
  Public `/api/config/public`, `/api/register`, `/api/me/*` never require the key.

## Shared object shapes

### ParticipantPublic

```json
{ "id": "uuid", "number": 1374, "first_name": "Имя", "last_name": "Фамилия",
  "token": "uuid-device-token", "created_at": "iso" }
```

### ParticipantShort

```json
{ "id": "uuid", "number": 1374, "first_name": "Имя", "last_name": "Фамилия" }
```

### ParticipantAdmin

```json
{ "id": "uuid", "number": 1374, "first_name": "Имя", "last_name": "Фамилия",
  "phone": "+77001234567" , "email": null, "company": null,
  "status": "ACTIVE", "status_reason": null,
  "created_at": "iso",
  "has_won": false,
  "pending_result": false }
```

- `status`: `ACTIVE | DISQUALIFIED | DELETED`
- `has_won`: has a `CONFIRMED` DrawResult in any draw.
- `pending_result`: has a `SELECTED` DrawResult (draw in `PENDING_CONFIRMATION`) — such a
  participant cannot be deleted/disqualified.

### DrawResultView

```json
{ "id": "uuid", "status": "SELECTED", "participant": ParticipantShort,
  "eligible_count": 847, "eligible_hash": "sha256-hex-64",
  "reason": null, "created_at": "iso" }
```

`status`: `SELECTED | CONFIRMED | REJECTED`.

### DrawView

```json
{ "id": "uuid", "position": 1, "title": "Розыгрыш №1", "prize": "Авиабилеты",
  "description": null, "status": "DRAFT",
  "exclude_previous_winners": null,
  "scheduled_at": null, "started_at": null, "completed_at": null, "created_at": "iso",
  "winner": null,
  "current_result": null }
```

- `status`: `DRAFT | PENDING_CONFIRMATION | COMPLETED | CANCELLED`
- `exclude_previous_winners`: `true | false | null` (null = use global setting).
- `winner`: `ParticipantShort | null` (set on COMPLETED).
- `current_result`: the `SELECTED` or `CONFIRMED` result (`DrawResultView`) or null.

### DrawDetail = DrawView +

```json
{ "eligible_count": 847,
  "effective_exclude_previous_winners": true,
  "results": [DrawResultView, ...] }
```

`results` sorted newest first. `eligible_count` is computed live at request time
(for a COMPLETED/CANCELLED draw it is still computed with the same rules; UI hides it).

### LiveSnapshot (REST `/api/live/current` and WS `state` event)

```json
{
  "type": "state",
  "state": "IDLE",
  "server_time": 1789000000000,
  "participants_count": 847,
  "event_name": "Kazakhstan Travel Forum 2026",
  "animation_duration_ms": 8000,
  "draw": null,
  "next_draw": null,
  "winner": null,
  "number_pool": null
}
```

- `state`: `IDLE | COUNTDOWN | DRAWING | WINNER | COMPLETED`.
  Backend persists only `IDLE`, `COUNTDOWN` (= draw running, `draw_id` set) and `COMPLETED`.
  When persisted state is `COUNTDOWN`, backend **derives** the reported state from
  `elapsed = now - started_at` of the *current SELECTED result*: `< 1000 ms → COUNTDOWN`,
  `< animation_duration_ms → DRAWING`, otherwise `WINNER`. The frontend does its own timing from
  `started_at` + `server_time` anyway; the derived value is for humans/tests.
- `draw`: `{ "id", "title", "prize", "started_at": <epoch ms | null> }` when state ≠ IDLE, else null.
  `started_at` is the `created_at` of the current `SELECTED`/`CONFIRMED` DrawResult
  (so a redraw restarts the animation clock), not `Draw.started_at`.
- `next_draw`: `{ "id", "title", "prize" } | null` — first `DRAFT` draw by `position` (shown in IDLE).
- `winner`: `{ "number", "first_name", "last_name" } | null` — the participant of the current
  SELECTED/CONFIRMED result when state ≠ IDLE.
- `number_pool`: `int[] | null` — sorted numbers of currently eligible participants for the
  draw (plus the winner's number), capped to 3000 entries; null in IDLE.
- `participants_count`: number of participants with status `ACTIVE`.

### Settings

```json
{
  "event_name": "Kazakhstan Travel Forum 2026",
  "event_slug": "ktf-2026",
  "registration_open": true,
  "allow_previous_winners": false,
  "start_number": 1000,
  "start_number_locked": false,
  "max_number": 2000,
  "on_max_reached": "continue",
  "timezone": "Asia/Almaty",
  "fields": {
    "phone":   { "enabled": false, "required": false },
    "email":   { "enabled": false, "required": false },
    "company": { "enabled": false, "required": false }
  },
  "animation": { "duration_ms": 8000, "sound": false }
}
```

`start_number_locked` is read-only (true once any participant exists).
`on_max_reached`: `"continue" | "close"`.

### AuditView

```json
{ "id": 123, "action": "DRAW_STARTED", "entity_type": "draw", "entity_id": "uuid",
  "participant_id": null, "draw_id": "uuid", "admin_login": "admin", "ip": "10.0.0.5",
  "metadata": { "eligible_count": 847, "eligible_hash": "..." }, "created_at": "iso" }
```

### Paginated list

```json
{ "items": [...], "total": 1234, "page": 1, "page_size": 50 }
```

## Public endpoints

### `GET /api/config/public`

```json
{ "event_name": "...", "registration_open": true,
  "fields": { "phone": {"enabled":false,"required":false}, "email": {...}, "company": {...} } }
```

### `POST /api/register`

Body: `{ "first_name", "last_name", "phone?", "email?", "company?", "device_token?" }`

- Names: trimmed, 1–60 chars, allowed: Cyrillic (incl. Kazakh letters), Latin, space, `-`, `'`.
- `phone`: normalised to E.164 (`+7XXXXXXXXXX`); accepts `8XXXXXXXXXX`, `7XXXXXXXXXX`, `+7 (XXX) ...`.
  Validated only if the field is enabled; required only if `required`.
- Disabled fields are ignored (not stored).
- `device_token` existing and participant `ACTIVE`/`DISQUALIFIED` → `200` with the **existing**
  record (idempotent). Otherwise a new participant is created → `201`.
- Response: `ParticipantPublic` (`token` is the device token to persist).
- Errors: `403 REGISTRATION_CLOSED`, `422 VALIDATION_ERROR`, `429 RATE_LIMITED`
  (soft, per IP, `REGISTER_RATE_LIMIT_PER_MIN`).
- Uses `X-Forwarded-For` (first value) / `X-Real-IP` for the IP when present.

### `GET /api/me/{token}`

`200 ParticipantPublic` for `ACTIVE` or `DISQUALIFIED` participant; `404 NOT_FOUND` if deleted or unknown.

### `GET /api/live/current`

`200 LiveSnapshot` (see key rule above).

### `GET /api/health`

`200 { "status": "ok", "db": true }` or `503 { "status": "error", "db": false }`.

### `WS /ws/live`

- On connect the server immediately sends a full `LiveSnapshot` (`type: "state"`).
- Server events:
  - `{"type":"state", ...LiveSnapshot}` — on every live-state change (start, redraw, confirm, idle,
    and also when a settings/draw change alters `next_draw`/`event_name`).
  - `{"type":"participants_count","count":847,"server_time":<ms>}` — debounced, ≤ 1 per 2 s.
  - `{"type":"ping","server_time":<ms>}` — every 15 s.
- Client may send `{"type":"pong"}` or anything; server ignores client messages.
- Client rule (both /draw and admin): after any (re)connect fetch `GET /api/live/current`;
  reconnect with backoff 1,2,4,…,10 s; if no message for 30 s, reconnect; if WS is unavailable,
  poll `/api/live/current` every 2 s.

## Admin endpoints (session cookie required unless stated)

### Auth

- `POST /api/admin/auth/login` body `{ "login", "password" }` → `200 { "login": "admin" }` + cookie.
  Errors: `401 INVALID_CREDENTIALS`, `429 TOO_MANY_ATTEMPTS` (5 failures / 5 min per IP → 5 min block).
- `POST /api/admin/auth/logout` → `204`, clears cookie.
- `GET /api/admin/auth/me` → `200 { "login" }` / `401 UNAUTHORIZED`.

### `GET /api/admin/stats`

```json
{ "total_participants": 847, "today_participants": 120,
  "draws_completed": 1, "winners_count": 1,
  "registration_open": true, "event_name": "...", "timezone": "Asia/Almaty",
  "public_base_url": "http://localhost", "live_state": "IDLE" }
```

`total_participants` counts `ACTIVE + DISQUALIFIED` (not deleted). `today_participants` — same,
created today in `timezone`.

### Participants

- `GET /api/admin/participants?q=&status=&won=&page=1&page_size=50&sort=number`
  - `q`: `ILIKE %q%` on first_name / last_name, OR exact match on `number` if `q` is an integer.
  - `status`: `ACTIVE | DISQUALIFIED | DELETED | all`; omitted ⇒ `ACTIVE + DISQUALIFIED`.
  - `won`: `true | false` (omitted ⇒ any).
  - `sort`: `number | -number | created_at | -created_at` (default `number`).
  - `page_size` 1..200, default 50.
  - → Paginated list of `ParticipantAdmin`.
- `GET /api/admin/participants/{id}` → `ParticipantAdmin` + `"results": [DrawResultView + "draw": {"id","title","prize"}]`.
- `POST /api/admin/participants/{id}/disqualify` body `{ "reason?" }` → `200 ParticipantAdmin`.
  Errors: `409 PARTICIPANT_HAS_PENDING_RESULT`, `409 INVALID_STATUS` (deleted).
- `POST /api/admin/participants/{id}/restore` → `200 ParticipantAdmin` (from DISQUALIFIED or DELETED).
- `DELETE /api/admin/participants/{id}` → `204`. Errors: `409 PARTICIPANT_HAS_PENDING_RESULT`.

### Draws

- `GET /api/admin/draws` → `{ "items": [DrawView] }` sorted by `position`, then `created_at`.
- `POST /api/admin/draws` body
  `{ "title", "prize", "description?", "position?", "scheduled_at?", "exclude_previous_winners?" }`
  → `201 DrawView`. `position` defaults to `max(position)+1`.
- `GET /api/admin/draws/{id}` → `200 DrawDetail`.
- `PATCH /api/admin/draws/{id}` (same fields as create, all optional) → `200 DrawView`.
  Error `409 DRAW_NOT_EDITABLE` unless status `DRAFT`.
- `DELETE /api/admin/draws/{id}` → `204`. Error `409 DRAW_NOT_DELETABLE` (not DRAFT or has results).
- `POST /api/admin/draws/{id}/cancel` → `200 DrawView`. `409 INVALID_STATUS` unless DRAFT.
- `POST /api/admin/draws/{id}/start` → `200 DrawDetail`.
  Errors: `409 INVALID_STATUS` (not DRAFT; `details.status` = current status),
  `409 ANOTHER_DRAW_ACTIVE` (`details.draw_id`), `409 NO_ELIGIBLE_PARTICIPANTS`.
- `POST /api/admin/draws/{id}/redraw` body `{ "reason?" }` → `200 DrawDetail`.
  Errors: `409 INVALID_STATUS` (not PENDING_CONFIRMATION), `409 NO_ELIGIBLE_PARTICIPANTS`.
- `POST /api/admin/draws/{id}/confirm` → `200 DrawDetail`. `409 INVALID_STATUS`.
- `POST /api/admin/live/idle` → `200 LiveSnapshot`. Allowed in any state; if a draw is
  `PENDING_CONFIRMATION` it stays pending (the screen just goes idle) — `409 DRAW_PENDING` is **not**
  raised; admin can still confirm/redraw later (redraw/confirm re-broadcasts state).

Concurrency: `start/redraw/confirm` lock the draw row (`SELECT … FOR UPDATE`) and the live-state
row; a second concurrent request gets `409 INVALID_STATUS` with the current state — never a second result.
Realtime events are published via PostgreSQL `NOTIFY` **inside the transaction** (delivered on
commit), so the WS broadcast always happens after commit and works from the CLI process too.

### Winners

`GET /api/admin/winners` →

```json
{ "items": [ { "draw_id": "uuid", "draw_position": 1, "draw_title": "...", "prize": "...",
               "participant_id": "uuid", "number": 1374, "first_name": "...", "last_name": "...",
               "confirmed_at": "iso" } ] }
```

Sorted by `confirmed_at`.

### Exports (CSV)

- `GET /api/admin/export/participants?status=&won=&q=` (same filters as list; default all non-deleted)
- `GET /api/admin/export/winners`
- `GET /api/admin/export/audit?action=&draw_id=&participant_id=`

Response `text/csv; charset=utf-8`, UTF-8 **with BOM**, delimiter `;`, CRLF,
`Content-Disposition: attachment; filename="{event_slug}_{kind}_{YYYY-MM-DD_HH-mm}.csv"`
(time in event timezone). CSV-injection guard: values starting with `= + - @` are prefixed with `'`.
Each export writes an `EXPORT` audit entry (`metadata.kind`).

Participants CSV columns: `number;first_name;last_name;phone;email;company;status;status_reason;has_won;created_at`
Winners CSV columns: `draw_position;draw_title;prize;number;first_name;last_name;confirmed_at`
Audit CSV columns: `id;created_at;action;entity_type;entity_id;participant_id;draw_id;admin_login;ip;metadata`
(`created_at` in event timezone, `YYYY-MM-DD HH:mm:ss`).

### Audit

`GET /api/admin/audit?action=&draw_id=&participant_id=&page=1&page_size=50` → Paginated `AuditView`,
newest first. `GET /api/admin/audit/actions` → `{ "items": ["ADMIN_LOGIN", ...] }` (distinct actions
present, for the filter dropdown).

### Settings

- `GET /api/admin/settings` → `Settings`.
- `PUT /api/admin/settings` body: any subset of `Settings` keys (partial update; nested `fields`
  and `animation` may also be partial). → `200 Settings`.
  Errors: `409 START_NUMBER_LOCKED` (start_number change when participants exist),
  `422 VALIDATION_ERROR`. Writes `SETTINGS_CHANGED` audit with `metadata.changes = { key: {old, new} }`.
  Changing `start_number` (while unlocked) also resets the number counter.

## Audit actions (backend writes, UI filters)

`PARTICIPANT_REGISTERED, PARTICIPANT_DISQUALIFIED, PARTICIPANT_RESTORED, PARTICIPANT_DELETED,
DRAW_CREATED, DRAW_UPDATED, DRAW_DELETED, DRAW_CANCELLED, DRAW_STARTED, WINNER_SELECTED, DRAW_REDRAW,
WINNER_CONFIRMED, SETTINGS_CHANGED, ADMIN_LOGIN, ADMIN_LOGIN_FAILED, EXPORT, LIVE_IDLE, SEED, RESET`

`admin_login` is `"cli"` for CLI actions, `null` for participant self-registration.

## Frontend routes

| Route | Purpose |
|---|---|
| `/` | Registration / my number |
| `/draw` | Live screen (optional `?key=`) |
| `/admin/login` | Login |
| `/admin` | Dashboard |
| `/admin/participants` | Participants table |
| `/admin/draws` | Draw list |
| `/admin/draws/[id]` | Draw page with START DRAW / confirm / redraw |
| `/admin/winners` | Winners |
| `/admin/settings` | Settings |
| `/admin/audit` | Audit log |
