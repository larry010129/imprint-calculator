#!/usr/bin/env bash
# One-time server setup. Run from the project root:
#   bash deploy/setup_server.sh
set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"
echo "Project root: $PROJECT_ROOT"

# 1. Virtualenv
if [ ! -d venv ]; then
  echo "Creating virtualenv..."
  python3 -m venv venv
fi
source venv/bin/activate

# 2. Dependencies
echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 3. .env
if [ ! -f .env ]; then
  cp deploy/pythonanywhere.env.example .env
  SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
  # Fill in a generated SECRET_KEY and this machine's project path
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET|" .env
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=sqlite:///$PROJECT_ROOT/database.db|" .env
  echo ""
  echo ">>> Created .env with a generated SECRET_KEY."
  echo ">>> EDIT .env now and set: ADMIN_PASSWORD, GOLD_XAU_PER_GRAM"
else
  echo ".env already exists - leaving it alone."
fi

# 4. Sanity check: app imports
echo "Checking that the app loads..."
python - <<'EOF'
from app import app
rules = sorted(r.rule for r in app.url_map.iter_rules())
print(f"OK - app loaded with {len(rules)} routes, e.g. {rules[:4]}")
EOF

echo ""
echo "Done. Next steps (PythonAnywhere Web tab):"
echo "  Source code : $PROJECT_ROOT"
echo "  Virtualenv  : $PROJECT_ROOT/venv"
echo "  Static files: /static/ -> $PROJECT_ROOT/static/"
echo "  WSGI file   : paste deploy/pythonanywhere.wsgi.example (fix PROJECT_HOME)"
echo "  Then click Reload."
