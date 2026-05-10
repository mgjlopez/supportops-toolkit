"""
migrate.py — Creates all database tables in SQL Server.
Run this once after `docker compose up` to initialize the schema.

Usage:
    docker compose exec api python db/migrate.py
"""

import sys
import time
import os

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import engine, Base, test_connection
import api.models  # noqa: F401 — registers all models with Base


def wait_for_db(retries=15, delay=5):
    print("⏳ Waiting for SQL Server to be ready...")
    for attempt in range(1, retries + 1):
        if test_connection():
            print("✅ SQL Server is ready.")
            return True
        print(f"   Attempt {attempt}/{retries} — retrying in {delay}s...")
        time.sleep(delay)
    print("❌ Could not connect to SQL Server. Check your .env and Docker logs.")
    return False


def create_database_if_not_exists():
    """
    SQL Server doesn't auto-create the database like SQLite does.
    We connect to 'master' first and create SupportOpsDB if needed.
    """
    from sqlalchemy import create_engine, text
    import os

    db_name = os.getenv("DB_NAME", "SupportOpsDB")
    server = os.getenv("DB_SERVER", "localhost")
    user = os.getenv("DB_USER", "sa")
    password = os.getenv("DB_PASSWORD", "")

    master_conn_str = (
        f"mssql+pyodbc://{user}:{password}@{server}/master"
        f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    master_engine = create_engine(master_conn_str)

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


def run_migrations():
    if not wait_for_db():
        sys.exit(1)

    print("\n📦 Creating database if needed...")
    create_database_if_not_exists()

    print("\n📋 Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created (or already existed).")
    print("\n🎉 Migration complete! You can now run: python db/seed.py")


if __name__ == "__main__":
    run_migrations()
