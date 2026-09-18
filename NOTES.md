# NOTES

## 2026-09-18
- Built the whole KTF 2026 live-draw system from `ktf_2026_draw_spec.md`: backend (FastAPI, SQLAlchemy async, Alembic, WS + PG LISTEN/NOTIFY, CLI, seed/reset, 45 pytest tests), frontend (Next.js 15: `/`, `/draw`, `/admin/*`), nginx, docker compose (db/backend/frontend/nginx/backup), README, `docs/API_CONTRACT.md`.
- Verified end-to-end via `docker compose up -d --build`: register → start (API) → redraw + confirm (CLI) → WS events → CSV/audit; headless-Chrome screenshots of all screens, no console errors, no external requests.
- Left: customer logo/brand assets (placeholder in `frontend/public/brand/`), Lighthouse run on a real phone, optional sound (TODO in DrawAnimation), HTTPS via external proxy. Repo is `git init`-ed but nothing committed yet.
- Gotchas: local port 5433 is taken by another project — backend tests need `TEST_DATABASE_URL=...localhost:5434...` (container `ktf-test-db` left running). `NEXT_PUBLIC_API_BASE` is baked at `next build`; for local dev use `next dev`. `.env` here has `SEED_DEMO=true` — run `scripts.reset --confirm` before a real event.
- Deployed to .188 (teleboom) as /root/FastNumber, port 8090 behind NPM (`nginx-app-1`, forward 172.17.0.1:8090), https://draw.ziz.kz (LE cert). Deploy key "teleboom (.188) read-only" on the GitHub repo. Update: `git pull && docker compose up -d --build backend frontend`.
- Registration form switched to one "ФИО" field (setting `name_mode`, default `full`): first word → last_name, rest → first_name; phone enable/required is toggled in Admin → Настройки.
- Gotcha: ziz.kz domain expires 2026-10-17 (ps.kz), renew before the event.
