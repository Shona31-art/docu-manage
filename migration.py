"""
migration.py
Handles schema upgrades for existing databases.

init_db() in database.py already creates tables fresh and adds missing
columns automatically — this module exists for explicit, named migrations
you might want to run by hand (e.g. after pulling new code, or before
deploying) rather than relying purely on the implicit check in init_db().
"""

import sqlite3
from database import DB_PATH


def _column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    return column in columns


def run_migrations():
    """Safe to run multiple times — every step checks before applying."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    changes = []

    # Ensure documents.company_id exists (older databases predating
    # multi-company support)
    if _table_exists(cur, "documents") and not _column_exists(cur, "documents", "company_id"):
        cur.execute("ALTER TABLE documents ADD COLUMN company_id INTEGER")
        changes.append("Added documents.company_id")

    # Ensure documents.file_hash exists (older databases predating
    # file-hash duplicate detection)
    if _table_exists(cur, "documents") and not _column_exists(cur, "documents", "file_hash"):
        cur.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT")
        changes.append("Added documents.file_hash")

    # Ensure documents.file_path exists (older databases predating
    # on-disk file storage / download-view-delete support)
    if _table_exists(cur, "documents") and not _column_exists(cur, "documents", "file_path"):
        cur.execute("ALTER TABLE documents ADD COLUMN file_path TEXT")
        changes.append("Added documents.file_path")

    conn.commit()
    conn.close()

    return changes


def _table_exists(cur, table):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cur.fetchone() is not None


if __name__ == "__main__":
    applied = run_migrations()
    if applied:
        print("Migrations applied:")
        for c in applied:
            print(f"  - {c}")
    else:
        print("Database already up to date, no migrations needed.")
