# Flask → Next.js migration plan

Goal: **zero Python in production**, hosted on **Vercel + Postgres**.

## Phase 1 — Core backend ✅ (this scaffold)

- [x] Prisma schema (9 models)
- [x] Validation, pricing, diamond options, order pricing
- [x] Metal price feed (env + BOT scrape)
- [x] APIs: catalog, quote, submit, prices, auth
- [x] SQLite → Postgres migration script
- [x] Flask password hash verification on login

## Phase 2 — Shop frontend (1–2 weeks)

- [ ] Port landing page to React (`marketing/`)
- [ ] Port calculator page — reuse or rewrite `shop/static/js/script.js` as TypeScript modules
- [ ] Wire shop to `/api/catalog`, `/api/quote`, `/api/submit`
- [ ] Session-aware nav (cart badge, gold ticker)
- [ ] Copy all CSS: `app-theme.css`, `landing.css`, `shop` styles

## Phase 3 — User features (1 week)

- [ ] Cart CRUD APIs + `/cart` page
- [ ] Favorites APIs + page
- [ ] Order history + search
- [ ] Profile + password change
- [ ] Share links `/s/[token]`
- [ ] Quote sheet PDF/page

## Phase 4 — Admin CMS (2–3 weeks)

- [ ] Admin auth guard
- [ ] Product CRUD + image upload (Vercel Blob / S3)
- [ ] Order management + status workflow
- [ ] Dashboard + CSV export
- [ ] Accounts + invite codes
- [ ] Notifications

## Phase 5 — Production cutover

- [ ] Neon Postgres populated via `migrate:sqlite`
- [ ] `copy-static` in CI before build
- [ ] Set `GOLD_XAU_PER_GRAM` or Vercel Cron for gold refresh
- [ ] DNS: `calculator.onrender.com` → Vercel custom domain
- [ ] Decommission Render Python service

## Data migration checklist

1. Backup `instance/database.db`
2. Create Neon database
3. `DATABASE_URL=... npx prisma db push`
4. `DATABASE_URL=... npm run migrate:sqlite`
5. `npm run copy-static`
6. Verify `/api/catalog` returns products
7. Test login with existing store account
8. Test chain 14K submit end-to-end

## Hosting comparison

| | Flask on Render | Next.js on Vercel |
|--|-----------------|-------------------|
| Runtime | Python + Waitress | Node serverless |
| Database | SQLite (fragile) | Postgres (Neon) |
| Deploy | Manual / git | Git push auto |
| Static CDN | Limited | Built-in |
| Cost | Free tier sleeps | Generous free tier |

## Files mapped from Python

| Python | TypeScript |
|--------|------------|
| `repository/models.py` | `prisma/schema.prisma` |
| `application/validation.py` | `src/lib/validation.ts` |
| `application/pricing.py` | `src/lib/pricing.ts` |
| `application/diamond_options.py` | `src/lib/diamond-options.ts` |
| `application/order_pricing.py` | `src/lib/order-pricing.ts` |
| `application/bot_metal_feed.py` | `src/lib/metal-feed.ts` |
| `gateway/routes.py` | `src/app/api/**/route.ts` + pages |
