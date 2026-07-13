#!/usr/bin/env python3
"""Trim bracelet product variants to business carat rules.

銘印手鍊 (sort_order 1): 0.1 ct only
Other bracelets: 0.1 and 0.2 ct only

Also runs automatically on app startup (sync_bracelet_variants).

Run: .venv\\Scripts\\python scripts/fix_bracelet_catalog.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')
os.environ.setdefault('SECRET_KEY', 'fix-bracelet-script-key')
os.environ.setdefault('DISABLE_PRICE_SCHEDULER', '1')

from diamond_calculator import create_app
from diamond_calculator.application.catalog_seed import sync_bracelet_variants


def main() -> None:
    app = create_app()
    with app.app_context():
        removed, added = sync_bracelet_variants()
        if removed or added:
            print(f'Done — removed {removed} variants, added {added} x 0.2 ct variants.')
        else:
            print('Bracelet catalog already up to date (or no bracelet products).')


if __name__ == '__main__':
    main()
