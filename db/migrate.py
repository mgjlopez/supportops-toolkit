"""
migrate.py — Creates all tables and seeds the lookup tables.

Lookup tables (priorities, statuses, categories, sources) are populated
here so the rest of the application can reference them by name safely.

Usage:
    docker compose exec api python db/migrate.py
"""

import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import engine, Base, test_connection, SessionLocal
import api.models as m


# Valid values for each lookup table
PRIORITIES = ["critical", "high", "medium", "low"]
STATUSES   = ["open", "in_progress", "escalated", "resolved", "closed"]
CATEGORIES = ["hardware", "software", "network", "access", "performance", "security", "other"]
SOURCES    = ["manual", "auto", "escalation"]


def wait_for_db(retries=15, delay=5):
    print("⏳ Waiting for SQL Server to be ready...")
    for attempt in range(1, retries + 1):
        if test_connection():
            print("✅ SQL Server is ready.")
            return True
        print(f"   Attempt {attempt}/{retries} — retrying in {delay}s...")
        time.sleep(delay)
    print("❌ Could not connect to SQL Server.")
    return False


def create_database_if_not_exists():
    from sqlalchemy import create_engine, text
    db_name  = os.getenv("DB_NAME",     "SupportOpsDB")
    server   = os.getenv("DB_SERVER",   "localhost")
    user     = os.getenv("DB_USER",     "sa")
    password = os.getenv("DB_PASSWORD", "")

    conn_str = (
        f"mssql+pyodbc://{user}:{password}@{server}/master"
        f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    master_engine = create_engine(conn_str)
    with master_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        exists = conn.execute(
            text("SELECT name FROM sys.databases WHERE name = :name"),
            {"name": db_name}
        ).fetchone()
        if not exists:
            conn.execute(text(f"CREATE DATABASE [{db_name}]"))
            print(f"✅ Database '{db_name}' created.")
        else:
            print(f"ℹ️  Database '{db_name}' already exists.")
    master_engine.dispose()


def seed_lookup_tables():
    """Insert the valid values into each lookup table (skip if already present)."""
    db = SessionLocal()
    try:
        def _seed(model, values):
            existing = {row.name for row in db.query(model).all()}
            for name in values:
                if name not in existing:
                    db.add(model(name=name))
            db.commit()

        _seed(m.TicketPriority, PRIORITIES)
        _seed(m.TicketStatus,   STATUSES)
        _seed(m.TicketCategory, CATEGORIES)
        _seed(m.TicketSource,   SOURCES)

        print("✅ Lookup tables seeded:")
        print(f"   Priorities : {PRIORITIES}")
        print(f"   Statuses   : {STATUSES}")
        print(f"   Categories : {CATEGORIES}")
        print(f"   Sources    : {SOURCES}")
    finally:
        db.close()


def run_migrations():
    if not wait_for_db():
        sys.exit(1)

    print("\n📦 Creating database if needed...")
    create_database_if_not_exists()

    print("\n📋 Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created (or already existed).")

    print("\n🔧 Seeding lookup tables...")
    seed_lookup_tables()

    print("\n🎉 Migration complete! You can now run: python db/seed.py")


if __name__ == "__main__":
    run_migrations()
