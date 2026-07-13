# Diamond Calculator

## What this is
This is an internal pricing and order tool for diamond rings and necklaces. It is built using Flask and uses a SQLite database to manage store submissions.

## Setup
Create a virtual environment, activate it, and install the dependencies:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Admin dashboard CSS (Tailwind):** after editing `admin/templates/` or `admin/static/css/cmsfullform.src.css`, rebuild:
```bash
npm install
npm run build:admin-css
```

**Cloud / production (no browser):** set `GOLD_XAU_PER_GRAM` and `DISABLE_BOT_SCRAPER=1` in `.env` — see Environment variables below. No Playwright install needed.

**Optional live scraping** (dev machine with Chromium): `pip install -r requirements-scraper.txt` then `playwright install chromium`.

## Environment variables

| Var | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | production: yes | session signing; sessions reset when changed. Optional only when `FLASK_DEBUG=1` (an ephemeral random key is generated per process). Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD` | first run only | seeds the `admin` account if it doesn't exist. Does **not** reset an existing admin's password |
| `FLASK_DEBUG` | dev only | `1` = Flask dev server with debugger. Leave unset (or `0`) in production — never expose the debugger publicly |
| `PORT` | no | server port, default 8000 (waitress) / 5000 (`flask run` dev server) |
| `HOST` | no | bind address, default `127.0.0.1`. Put nginx (or another reverse proxy) in front rather than binding `0.0.0.0` directly |
| `DATABASE_URL` | no | overrides the default `sqlite:///database.db`; use a `postgresql://...` URL in production (see "Production database" below) |
| `TRUSTED_PROXY_COUNT` | no | number of reverse-proxy hops to trust for `X-Forwarded-*` headers (default `1`). Set to `0` if the app is reachable directly with no proxy |
| `RATELIMIT_STORAGE_URI` | recommended in production | backend for login/register rate limiting, e.g. `redis://host:6379`. Defaults to in-process memory, which resets on restart |
| `LOG_LEVEL` | no | Python logging level, default `INFO` (`DEBUG` when `FLASK_DEBUG=1`) |
| `LOG_FILE` | no | if set, also writes logs to this file path in addition to stdout |
| `GOLD_XAU_PER_GRAM` | cloud: yes | manual gold price in TWD/gram (黃金條塊 本行賣出). Set this on servers without a browser; update when [BOT rates](https://rate.bot.com.tw/gold/quote/recent) change |
| `DISABLE_BOT_SCRAPER` | cloud: recommended | `1` skips Playwright/browser scraping. Pair with `GOLD_XAU_PER_GRAM` on cloud deploys |

*Note: Changing the `SECRET_KEY` will invalidate all active sessions and log everyone out.*

Copy `.env.example` to `.env` and fill in real values for local dev. The app auto-loads `.env` on startup via `python-dotenv` (see `load_dotenv()` in `app.py`); shell `set`/`export` still works and overrides `.env` if both are set.

## Run
**Development**:
```bash
set FLASK_DEBUG=1
python app.py
```

**Production** (see "Deploying to the public internet" below for the full nginx + TLS setup):
```bash
set SECRET_KEY=your_secure_secret_key
python app.py
```
This serves the application on `http://127.0.0.1:8000` via Waitress — bound to localhost only, not exposed to the network by itself. Put a reverse proxy (nginx) in front of it to terminate TLS and expose it publicly; see below.

## First run
Set `ADMIN_PASSWORD` and start the server once. This will seed the `admin` account (only if it doesn't already exist). Log in as `admin`, change the seeded password immediately from the admin accounts page, and stores can self-register at `/register`.
Example:
```bash
set ADMIN_PASSWORD=supersecret
python app.py
```

## Gold price source
Gold pricing lives in `diamond_calculator/application/bot_metal_feed.py`. Gold (`XAU`) uses BOT **黃金條塊** 「本行賣出」 (NT$/gram from the 1 kg column). Source: [BOT gold bar history quote](https://rate.bot.com.tw/gold/quote/recent). Platinum (`XPT`) and silver (`XAG`) use hardcoded fallback constants.

**Cloud / production (no browser):** set `GOLD_XAU_PER_GRAM` and `DISABLE_BOT_SCRAPER=1` in `.env`. The app serves that price immediately — no Playwright or `playwright install chromium` needed. Update `GOLD_XAU_PER_GRAM` when BOT changes rates.

**Optional live scraping (dev):** install `requirements-scraper.txt` and run `playwright install chromium`. The scraper tries plain HTTP first, then a headless browser if BOT serves a bot challenge (~45–75s). Successful scrapes are cached in `instance/gold_price_cache.json`. If scraping fails, the app keeps the last cached price; `FALLBACK_TWD_PER_GRAM` is only used when nothing else is available.

- Background refresh: once shortly after startup, then daily at 03:00 Asia/Taipei, and on-demand via `/api/gold/refresh` (debounced to 60s).
- Deploying behind nginx with live scraping: `/api/gold/refresh` may need a longer `proxy_read_timeout` (~75s); see `deploy/nginx.conf.example`. Not needed when `DISABLE_BOT_SCRAPER=1`.

## Deploying to the public internet

This app is designed to sit behind a reverse proxy that terminates TLS. Example configs are in `deploy/`:

1. Provision a Linux server, install Python 3.11+, nginx, and certbot.
2. Copy the repo to e.g. `/opt/diamond-calculator`, create a venv, and `pip install -r requirements.txt`.
3. Create `/opt/diamond-calculator/.env` with a real `SECRET_KEY`, `ADMIN_PASSWORD` (first run only), `PORT=8000`, `GOLD_XAU_PER_GRAM` (current BOT 黃金條塊 sell price per gram), and `DISABLE_BOT_SCRAPER=1`. For PostgreSQL, also set `DATABASE_URL`.
   - **Optional:** live BOT scraping instead of manual price — `pip install -r requirements-scraper.txt` then `playwright install --with-deps chromium` (omit `DISABLE_BOT_SCRAPER`).
4. Install `deploy/diamond-calculator.service` to `/etc/systemd/system/`, then:
   ```bash
   sudo systemctl enable --now diamond-calculator
   ```
5. Point DNS for your domain at the server, then install `deploy/nginx.conf.example` to `/etc/nginx/sites-available/diamond-calculator` (edit `server_name` and paths), symlink it into `sites-enabled`, and reload nginx.
6. Issue a certificate: `sudo certbot --nginx -d your-domain.example` (installs and auto-renews a Let's Encrypt certificate, and edits the nginx config to add the TLS block).
7. Confirm `TRUSTED_PROXY_COUNT=1` (the default) matches the nginx config, which sets exactly one hop of `X-Forwarded-For`/`X-Forwarded-Proto`.

Waitress should never be exposed directly to the internet — always put nginx (or another TLS-terminating proxy) in front of it.

## Production database & migrations
By default the app uses SQLite (`instance/database.db`) and auto-creates its schema on startup — zero config, fine for a handful of stores. For a public production deployment, point `DATABASE_URL` at Postgres instead, e.g.:
```
DATABASE_URL=postgresql://user:password@host:5432/diamond_calculator
```
Install a Postgres driver (`pip install psycopg[binary]`) alongside `requirements.txt`. Postgres (or any non-SQLite `DATABASE_URL`) does **not** auto-create tables — instead, schema is managed with Flask-Migrate/Alembic (`migrations/`), so changes are reviewable instead of silently applied:
```bash
set FLASK_APP=app:app
python -m flask db upgrade
```
Run `flask db upgrade` once against a fresh Postgres database before the first start (this creates all tables from `migrations/versions/`), and again after pulling any change that includes a new migration. If you change the models (`diamond_calculator/repository/models.py`), generate a new migration with:
```bash
python -m flask db migrate -m "describe the change"
python -m flask db upgrade
```

## Data & backup
All data lives in `instance/database.db`. To back it up, copy that file while the server is stopped, or run the following while it is running:
```bash
sqlite3 instance/database.db ".backup backup.db"
```

## Product images
Images are located in `static/images/`, organized by color folder (`white/`, `yellow/`, `rose/`). Refer to `static/images/README.md` for the full naming convention. They're deployed from the root-level `image/` source folder via `python scripts/deploy_product_assets.py`; re-run it whenever those source assets change.

The Chinese-named folders under `image/` (`戒指`, `墜子`, `耳飾`, `手鍊`, `鍊條`) are original JPG reference assets. They are intentionally not used by the deploy script, which reads only the ASCII `silver`, `rose_gold`, and `gold` folders. Some Windows terminals may display those Chinese folder names as mojibake; do not rename them based only on terminal output.

## Testing
Run the tests with:
```bash
python tests/test_validation.py
python tests/test_routes.py
python tests/test_bot_metal_feed.py
```
All three are plain assert-based scripts (no pytest). `test_routes.py` uses an in-memory SQLite database and never touches `instance/database.db`.
