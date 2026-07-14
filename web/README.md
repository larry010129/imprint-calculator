# Imprint Calculator — TypeScript / Next.js

Full rewrite of the Flask app in **Next.js + TypeScript + Postgres**. Deploy on **Vercel** (frontend + API) with **Neon** or **Supabase** Postgres — no Python runtime required.

## Stack

| Layer | Tech |
|-------|------|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript |
| Database | PostgreSQL via Prisma |
| Auth | Cookie session + bcrypt (Flask password hash compatible on login) |
| Pricing | Ported from `order_pricing.py` / `pricing.py` |
| Gold prices | BOT scrape + env override (`GOLD_XAU_PER_GRAM`) |

## Quick start

```bash
cd web
cp .env.example .env.local
# Set DATABASE_URL to Postgres (Neon free tier works)

npm install
npx prisma generate
npx prisma db push

# Copy product images from the Python app
npm run copy-static

# Migrate existing SQLite data (optional)
npm run migrate:sqlite

npm run dev
```

Open http://localhost:3000

## Environment

See `.env.example`. Required:

- `DATABASE_URL` — Postgres connection string
- `SESSION_SECRET` — random string (future signed sessions)

Optional:

- `GOLD_XAU_PER_GRAM` — fixed gold price (recommended on Vercel; no background scraper)
- `DISABLE_BOT_SCRAPER=1` — use cache/env only
- `SQLITE_PATH` — path to old `instance/database.db` for migration

## Deploy (Vercel + Neon) — recommended

1. Create a **Neon** Postgres database → copy `DATABASE_URL`
2. Push this `web/` folder to GitHub
3. **Vercel** → Import project → Root directory: `web`
4. Environment variables: `DATABASE_URL`, `GOLD_XAU_PER_GRAM`, `SESSION_SECRET`
5. Build command: `npm run build` (runs `prisma generate` via postinstall)
6. Run `npx prisma db push` once against production DB (or use migrations)
7. Run `npm run migrate:sqlite` locally pointing at production `DATABASE_URL` to import data

### Why this is easier hosting

- **No Python process** on Render
- **Serverless API routes** scale automatically on Vercel
- **Managed Postgres** — data never wiped on deploy (unlike SQLite on Render free tier)
- **Static assets** on CDN via `public/static`
- Gold price via **env var** or Vercel Cron hitting `/api/gold/refresh` (add when needed)

## API parity (Phase 1 — done)

| Endpoint | Status |
|----------|--------|
| `GET /api/health` | ✅ |
| `GET /api/catalog` | ✅ |
| `POST /api/quote` | ✅ |
| `POST /api/submit` | ✅ |
| `GET /api/prices` | ✅ |
| `POST /api/auth/login` | ✅ |
| `POST /api/auth/logout` | ✅ |
| `GET /api/auth/me` | ✅ |

## Still to port (Phase 2–4)

See [MIGRATION.md](./MIGRATION.md) for the full checklist:

- Cart, favorites, notifications APIs
- Admin CMS (products, orders, invites, dashboard)
- SSR pages: landing, calculator UI, history, profile
- File uploads → Vercel Blob / S3
- Rate limiting, CSRF, audit log
- Email / invite registration flow

## Running alongside Flask (transition)

During migration you can:

1. Point the existing `shop/static/js/script.js` at `https://your-next-app.vercel.app/api/*`
2. Keep Flask for admin only until Phase 3
3. Cut over DNS when calculator + orders work on Next.js

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Local dev server |
| `npm run build` | Production build |
| `npm run copy-static` | Copy `../static` → `public/static` |
| `npm run migrate:sqlite` | Import SQLite DB into Postgres |
| `npm run db:push` | Apply Prisma schema |
