# Deployment guide

The app has one production entry point: **`wsgi.py`** (exposes `application`).
Docker / Render use **`Dockerfile`** → Waitress via `app.py`.

---

## Option 0: Render (recommended for a public website)

1. Push this repo to GitHub.
2. In [Render](https://dashboard.render.com/) → **New** → **Blueprint** → select the repo
   (uses `render.yaml`), **or** **New Web Service** → Docker, root directory `.`.
3. Set environment variables in the dashboard:

| Var | Required | Notes |
|---|---|---|
| `SECRET_KEY` | yes | auto-generated if using Blueprint |
| `ADMIN_PASSWORD` | first run | seeds the `admin` account |
| `GOLD_XAU_PER_GRAM` | yes | TWD/gram gold price |
| `DATABASE_URL` | yes | auto-linked from Render Postgres if using Blueprint |

4. Deploy. Open `https://<your-service>.onrender.com/health` to confirm.

**Why the previous build failed:** the Dockerfile used Python 3.9, but
`psycopg==3.3.4` needs Python ≥ 3.10. It now uses **Python 3.12**.

After fixing, push and redeploy (or click **Manual Deploy** → **Clear build cache & deploy**).

---

## Option 1: PythonAnywhere (your current host)

### First-time setup

Open a **Bash console** on PythonAnywhere:

```bash
cd ~
git clone <YOUR_GITHUB_REPO_URL> calculator/imprint-calculator
cd calculator/imprint-calculator
bash deploy/setup_server.sh
nano .env    # set ADMIN_PASSWORD and GOLD_XAU_PER_GRAM (SECRET_KEY is auto-generated)
```

### Web tab configuration

| Setting | Value |
|---|---|
| Source code | `/home/yuzi010129/calculator/imprint-calculator` |
| Virtualenv | `/home/yuzi010129/calculator/imprint-calculator/venv` |
| Static files | URL `/static/` → `/home/yuzi010129/calculator/imprint-calculator/static/` |

**WSGI configuration file** (`/var/www/yuzi010129_pythonanywhere_com_wsgi.py`) —
delete everything and paste the contents of `deploy/pythonanywhere.wsgi.example`.
It boils down to:

```python
import os, sys
PROJECT_HOME = '/home/yuzi010129/calculator/imprint-calculator'
if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)
os.chdir(PROJECT_HOME)
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_HOME, '.env'), override=True)
from app import app as application
```

Click the green **Reload** button. Visit `/health` to confirm.

> Still seeing "Hello from Flask!"? The WSGI file is loading a different
> folder (usually `~/mysite`). Verify with:
> `head -3 /home/yuzi010129/calculator/imprint-calculator/app.py`
> — it must start with `"""Server entry point...`.

### Updating after a git push

```bash
cd ~/calculator/imprint-calculator
git pull
venv/bin/pip install -r requirements.txt
```

Then hit **Reload** on the Web tab.

---

## Option 2: Docker (any VPS)

```bash
cp docker-compose.env.example .env   # fill in secrets
docker compose up --build -d
```

Serves on port 8000 with Postgres and Redis included. See `docker-compose.yml`.

---

## Option 3: Linux + systemd + nginx

Follow "Deploying to the public internet" in `README.md`, using:

- `deploy/diamond-calculator.service` (systemd unit, runs Waitress)
- `deploy/nginx.conf.example` (TLS-terminating reverse proxy)

---

## Environment variables (production minimum)

| Var | Purpose |
|---|---|
| `SECRET_KEY` | session signing — required, generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD` | seeds the `admin` account on first run only |
| `GOLD_XAU_PER_GRAM` | manual gold price (TWD/gram) for hosts without a browser |
| `DISABLE_BOT_SCRAPER=1` | skip Playwright scraping on cloud hosts |
| `DATABASE_URL` | optional; Postgres in production (`flask db upgrade` required) |

Full list: `.env.example`.
