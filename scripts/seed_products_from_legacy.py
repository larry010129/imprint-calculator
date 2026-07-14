#!/usr/bin/env python3
"""One-time seed: convert the hardcoded 13 style slots into Product rows.

Reads today's hardcoded STYLE_LABELS / WEIGHT_TABLE / CHAIN_WEIGHT_CHIN and
creates matching Product + ProductVariant + ProductImage rows, all
is_published=True, pointing at the already-deployed static/images/ files
(no copying needed). Safe to re-run: skips seeding if any Product row
already exists.

Run (after `flask db upgrade`):
  .venv\\Scripts\\python scripts/seed_products_from_legacy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=True)

from diamond_calculator import create_app
from diamond_calculator.application.catalog_seed import seed_legacy_products


def main() -> None:
    app = create_app()
    with app.app_context():
        created = seed_legacy_products()
        if created:
            print(f'Seeded {created} products.')
        else:
            print('Products already exist — skipping seed (delete existing rows first if you want to re-seed).')


if __name__ == '__main__':
    main()
