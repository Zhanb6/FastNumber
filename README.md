# KTF 2026 — Live Draw System

Web application for running public prize draws during an event:
QR code → registration → unique number → live draws launched by the organiser and shown on the stage screen.

| Screen | URL | Device |
|---|---|---|
| Registration | `http://<host>/` | Attendee's phone |
| Live Draw Screen | `http://<host>/draw` | TV / projector / LED (1920×1080) |
| Admin Panel | `http://<host>/admin` | Organiser's laptop |

Stack: FastAPI + PostgreSQL 16 + Next.js (App Router) behind nginx, all in `docker compose`.
No external services are used at runtime — the system works on a local network without internet.

---

## 1. Quick start

Requirements: Docker Desktop / Docker Engine with `docker compose`.

```bash
cp .env.example .env
# edit .env: POSTGRES_PASSWORD, SECRET_KEY, ADMIN_PASSWORD, PUBLIC_BASE_URL
docker compose up -d --build
```

After the containers are healthy:

| URL | Screen |
|---|---|
| `http://localhost/` | Registration |
| `http://localhost/draw` | Live Draw Screen |
| `http://localhost/admin` | Admin Panel (login/password from `.env`) |

Alembic migrations run automatically when the backend starts.
Change the exposed port with `HTTP_PORT` in `.env` (default `80`).

### Demo data

```bash
docker compose exec backend python -m scripts.seed
```

Creates 50 test participants and a demo draw ("Демо-розыгрыш" / "Демо-приз").
Set `SEED_DEMO=true` in `.env` to seed automatically on the first start with an empty database.

Wipe demo data before the real event (irreversible, logged to the audit log):

```bash
docker compose exec backend python -m scripts.reset --confirm
```

---

## 2. Configuration

### `.env` (secrets and first-run defaults)

| Variable | Meaning |
|---|---|
| `POSTGRES_DB/USER/PASSWORD` | Database credentials (used by `db`, `backend`, `backup`) |
| `SECRET_KEY` | Signs admin session cookies. Long random string. |
| `ADMIN_LOGIN`, `ADMIN_PASSWORD` | Admin credentials; the bcrypt hash is (re)written at backend start |
| `PUBLIC_BASE_URL` | Public URL of the system, used for the QR code and CSRF checks |
| `DRAW_SCREEN_KEY` | Optional. If set, `/draw?key=<value>` is required to open the live screen |
| `COOKIE_SECURE` | Optional. Force the `Secure` flag on the admin cookie (default: on when `PUBLIC_BASE_URL` is https) |
| `EVENT_NAME`, `EVENT_SLUG`, `EVENT_TIMEZONE` | Event defaults (first run only, then editable in Admin → Настройки) |
| `START_NUMBER`, `MAX_NUMBER`, `ON_MAX_REACHED` | Numbering defaults (`continue` or `close` when `MAX_NUMBER` is reached) |
| `NAME_MODE` | Registration name input: `full` (one ФИО field, first word = surname) or `split` (first + last name) |
| `ALLOW_PREVIOUS_WINNERS`, `REGISTRATION_OPEN` | Draw and registration defaults |
| `REGISTER_RATE_LIMIT_PER_MIN` | Soft per-IP limit for registrations (shared venue NAT — keep it generous) |
| `SEED_DEMO` | `true` → seed demo data on first start |
| `HTTP_PORT` | Host port for nginx |
| `BACKUP_INTERVAL_SECONDS`, `BACKUP_KEEP` | Backup period (default 15 min) and how many dumps to keep |

Event defaults are copied into the `settings` table on the first start. After that the values in
**Admin → Настройки** take priority; changing `.env` does not overwrite them.

### Admin → Настройки

- Event name, registration open/closed
- "Исключать предыдущих победителей" (global; can be overridden per draw)
- Name input format: one ФИО field or separate first/last name
- Optional form fields (phone, email, company): enabled / required
- Behaviour when `maxNumber` is reached
- Start number — editable only until the first registration

### Branding

- `frontend/src/config/branding.ts` — event name lines, colours, logo path
- `frontend/public/brand/` — logo and brand assets (replace the placeholder with the customer's logo)
- `frontend/src/i18n/` — all UI texts (Russian; add `kk`/`en` dictionaries alongside)

Fonts are self-hosted (Inter, Cyrillic + Kazakh letters). No CDN.

---

## 3. Pre-event checklist

1. `.env`: strong `POSTGRES_PASSWORD`, `SECRET_KEY`, `ADMIN_PASSWORD`; `PUBLIC_BASE_URL` = the URL printed on the QR code.
2. `docker compose up -d --build` on the event machine; `docker compose ps` shows every service `healthy`.
3. Demo data wiped: `docker compose exec backend python -m scripts.reset --confirm`.
4. Admin → Настройки: event name, start number, optional fields, "exclude previous winners".
5. Admin → Розыгрыши: create all draws with the correct order, title and prize.
6. Admin → Dashboard: print the QR code (it points to `PUBLIC_BASE_URL`). Scan it from a phone on the venue Wi-Fi and register a test participant, then delete it in Admin → Участники (the number is not reused; that's expected).
7. Open `http://<host>/draw` on the stage PC, press `F` for fullscreen, check the green dot in the corner.
8. Run a test draw end-to-end (start → screen animation → confirm), then delete/cancel it or use a dedicated test draw.
9. Check `./backups/` contains fresh `*.sql.gz` files.
10. Registration: Admin → Dashboard toggle "Регистрация открыта".
11. DevTools → Network on all three screens: no requests to external domains.

---

## 4. Running a draw (normal procedure)

1. Admin → Розыгрыши → open the draw. Check "Eligible участников".
2. Press **START DRAW** → confirm "Запустить розыгрыш среди N участников?".
3. The winner is selected and stored on the server **before** the screen starts animating (8 s: title → fast numbers → slow-down → reveal + confetti).
4. Admin sees the winner immediately; the "Подтвердить победителя" / "Повторить розыгрыш" buttons unlock after the 8 s animation.
5. Winner is present → **Подтвердить победителя**. Winner is absent → **Повторить розыгрыш** (optional reason). The rejected participant is kept in history and excluded from this round's redraw.
6. When the stage is done with the winner card → **Вернуть экран в режим ожидания**.

Rules enforced by the backend:

- Only one draw can be active at a time; double clicks / duplicate requests never create a second result.
- A `COMPLETED` draw cannot be changed via UI or API.
- Every action is written to the append-only Audit Log (with eligible count and a SHA-256 of the eligible number list for each start/redraw).

---

## 5. Emergency procedures

### The admin panel is unreachable but the server is up — run the draw from the server console

```bash
docker compose exec backend python -m scripts.draw_cli list
docker compose exec backend python -m scripts.draw_cli start <draw_id|position>
docker compose exec backend python -m scripts.draw_cli redraw <draw_id|position> --reason "winner absent"
docker compose exec backend python -m scripts.draw_cli confirm <draw_id|position>
docker compose exec backend python -m scripts.draw_cli idle
```

The CLI uses the same service code as the API, writes to the Audit Log as `cli`, and the live screen
reacts exactly as if the button had been pressed in the admin panel.

### The live screen lost connection

The screen reconnects automatically (backoff up to 10 s) and reloads the current state from the
database. If the browser itself is stuck: reload the page (`F5`) — the screen restores the current
state, including a draw in progress. Press `F` for fullscreen again.

### A container died

```bash
docker compose ps
docker compose logs --tail=200 backend
docker compose up -d            # restarts anything that is down
```

All containers have `restart: unless-stopped`; database data lives in the named volume `pgdata`.

### Export everything right now

Admin → Участники → "Экспорт CSV", Admin → Победители → "Скачать CSV", Admin → Audit Log → "Скачать CSV".
Or from the console:

```bash
docker compose exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > manual_backup.sql.gz
```

---

## 6. Backups

The `backup` service runs `pg_dump` every `BACKUP_INTERVAL_SECONDS` (default 15 min) into `./backups/`
and keeps the newest `BACKUP_KEEP` files (default 96 = 24 h).

Restore into a fresh database:

```bash
docker compose stop backend
gunzip -c backups/eventdraw_2026-09-18_10-00-00.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose start backend
```

(For a full reset first drop and recreate the database, or `docker compose down` and remove the
`pgdata` volume deliberately.)

---

## 7. HTTPS

nginx in this repo listens on plain HTTP (port `HTTP_PORT`). For HTTPS put an external reverse proxy
(Caddy, Traefik, Nginx Proxy Manager, hosting-provided TLS) in front of it and point it to
`http://<host>:<HTTP_PORT>`. Set `PUBLIC_BASE_URL=https://...` in `.env` — this turns on the
`Secure` flag for the admin cookie and updates the QR code.

Minimal Caddy example (`Caddyfile` on the host):

```
draw.example.kz {
    reverse_proxy 127.0.0.1:8080
}
```

with `HTTP_PORT=8080`.

---

## 8. Personal data

The system stores first name, last name, optional phone/email/company, a random device token, IP and
user-agent (for abuse investigation only). After the event:

1. Export what you need to keep (winners CSV).
2. Delete the data:

```bash
docker compose down
docker volume rm <project>_pgdata      # `docker volume ls` shows the exact name
rm -rf backups/*.sql.gz
```

---

## 9. Reusing for another event

1. Copy the repo, create a new `.env` (`EVENT_NAME`, `EVENT_SLUG`, `START_NUMBER`, ...).
2. Replace `frontend/public/brand/*` and adjust `frontend/src/config/branding.ts` (name lines, colours).
3. Optionally translate `frontend/src/i18n/`.
4. `docker compose up -d --build` on a clean machine → empty database, defaults from `.env`.

No business logic changes are needed.

---

## 10. Development

### Backend

```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
docker run -d --name ktf-test-db -p 5433:5432 -e POSTGRES_USER=eventdraw -e POSTGRES_PASSWORD=eventdraw -e POSTGRES_DB=eventdraw_test postgres:16-alpine
export DATABASE_URL=postgresql+asyncpg://eventdraw:eventdraw@localhost:5433/eventdraw_test
export SECRET_KEY=dev ADMIN_LOGIN=admin ADMIN_PASSWORD=admin ALLOWED_ORIGINS=http://localhost:3000
alembic upgrade head
uvicorn app.main:app --reload --port 8000
pytest -q          # tests use TEST_DATABASE_URL (same default as above)
ruff check . && ruff format --check .
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000, API at NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run build && npm run lint
```

### Layout

```
backend/     FastAPI app, Alembic migrations, scripts (seed, reset, draw_cli), pytest
frontend/    Next.js app: /, /draw, /admin/*
nginx/       reverse proxy config (single entry point)
scripts/     backup.sh (pg_dump loop)
docs/        API_CONTRACT.md (backend ⇄ frontend contract)
ktf_2026_draw_spec.md   original specification
```
