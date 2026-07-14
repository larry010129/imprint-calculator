#!/usr/bin/env python3
"""Import users, submissions, and notifications from a legacy SQLite database.db
into the current Postgres (Neon) database.

Usage:
  .venv\\Scripts\\python scripts/migrate_sqlite_to_postgres.py path\\to\\database.db
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env', override=True)

from diamond_calculator import create_app
from diamond_calculator.repository.models import Product, Submission, User, UserNotification, db


def _product_id(category: str, style_type: str | None) -> int | None:
    if not category or not style_type or len(str(style_type)) != 1:
        return None
    sort_order = ord(str(style_type).upper()) - ord('A')
    product = Product.query.filter_by(category=category, sort_order=sort_order).first()
    return product.id if product else None


def _normalize_carat(carat: str | None) -> str | None:
    if carat is None:
        return None
    carat = str(carat)
    if carat == '1':
        return '1.0'
    return carat


def migrate(sqlite_path: Path) -> None:
    if not sqlite_path.is_file():
        raise SystemExit(f'File not found: {sqlite_path}')

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    user_map: dict[int, int] = {}

    print('Importing users…')
    for row in cur.execute('SELECT * FROM user ORDER BY id'):
        existing = User.query.filter_by(username=row['username']).first()
        if existing:
            existing.password_hash = row['password_hash']
            existing.role = row['role']
            existing.store_name = row['store_name']
            user_map[row['id']] = existing.id
            print(f"  updated {row['username']} (id {row['id']} -> {existing.id})")
        else:
            user = User(
                username=row['username'],
                password_hash=row['password_hash'],
                role=row['role'],
                store_name=row['store_name'],
            )
            db.session.add(user)
            db.session.flush()
            user_map[row['id']] = user.id
            print(f"  created {row['username']} (id {row['id']} -> {user.id})")

    db.session.commit()

    print('Importing submissions…')
    imported_subs = 0
    for row in cur.execute('SELECT * FROM submission ORDER BY id'):
        if Submission.query.filter_by(id=row['id']).first():
            print(f"  skip submission #{row['id']} (already exists)")
            continue
        new_user_id = user_map.get(row['user_id'])
        if not new_user_id:
            print(f"  skip submission #{row['id']} (unknown user_id {row['user_id']})")
            continue
        category = row['category']
        style_type = row['style_type']
        sub = Submission(
            id=row['id'],
            user_id=new_user_id,
            product_id=_product_id(category, style_type),
            category=category,
            carat=_normalize_carat(row['carat']),
            style_type=style_type,
            gold_purity=row['gold_purity'],
            color=row['color'],
            weight=row['weight'],
            ring_size=row['ring_size'],
            total_price=row['total_price'],
            gold_rate_per_gram=row['gold_rate_per_gram'],
            price_source=row['price_source'],
            status=row['status'] or 'pending',
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            diamond_kind='white',
            diamond_shape='round',
            include_chain=False,
        )
        db.session.add(sub)
        imported_subs += 1
        print(f"  imported submission #{row['id']} for user_id {new_user_id}")

    db.session.commit()

    print('Importing notifications…')
    imported_notes = 0
    for row in cur.execute('SELECT * FROM user_notification ORDER BY id'):
        if UserNotification.query.filter_by(id=row['id']).first():
            print(f"  skip notification #{row['id']} (already exists)")
            continue
        new_user_id = user_map.get(row['user_id'])
        if not new_user_id:
            print(f"  skip notification #{row['id']} (unknown user_id {row['user_id']})")
            continue
        note = UserNotification(
            id=row['id'],
            user_id=new_user_id,
            kind=row['kind'],
            message=row['message'],
            order_id=row['order_id'],
            order_summary=row['order_summary'],
            is_read=bool(row['is_read']),
            created_at=row['created_at'],
        )
        db.session.add(note)
        imported_notes += 1
        print(f"  imported notification #{row['id']}")

    db.session.commit()

    # Keep Postgres id sequences ahead of imported ids.
    for table, model in (
        ('user', User),
        ('submission', Submission),
        ('user_notification', UserNotification),
    ):
        max_id = db.session.query(db.func.max(model.id)).scalar() or 0
        if max_id:
            seq = f'"{table}"' if table == 'user' else table
            db.session.execute(
                db.text(f"SELECT setval(pg_get_serial_sequence('{seq}', 'id'), :val, true)"),
                {'val': max_id},
            )
    db.session.commit()

    conn.close()
    print(
        f'\nDone. users={len(user_map)} submissions={imported_subs} '
        f'notifications={imported_notes}'
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f'Usage: {Path(__file__).name} <path-to-database.db>')
    app = create_app()
    with app.app_context():
        migrate(Path(sys.argv[1]))


if __name__ == '__main__':
    main()
