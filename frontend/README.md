# Frontend (Next.js 15, App Router)

Routes: `/` registration, `/draw` live screen (`?key=` optional), `/admin/*` admin panel.
API contract: `../docs/API_CONTRACT.md`.

## Develop

```bash
npm install
npm run dev        # http://localhost:3000, API at http://localhost:8000 (.env.development)
npm run lint && npx tsc --noEmit
npm run build      # standalone output (.next/standalone)
```

`NEXT_PUBLIC_API_BASE` is inlined at build time: empty in production (same origin via nginx,
`.env.production`), `http://localhost:8000` in dev.

## Branding

Texts, tagline, colours: `src/config/branding.ts`. Logo: `public/brand/logo.svg` (see `public/brand/README.md`).
UI strings: `src/i18n/ru.ts` (add `kk.ts`/`en.ts` with the same keys and register in `src/i18n/index.ts`).

## Live screen

`/draw` — press `F` for fullscreen; cursor hides after 3 s; the dot bottom-right shows connection state
(green connected, amber reconnecting). The animation timeline is driven by `started_at` + server time,
so a screen opened mid-draw joins at the right phase.
