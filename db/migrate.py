"""
migrate.py — Creates all tables and seeds lookup + user data.
"""

import sys, time, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import engine, Base, test_connection, SessionLocal
from api.auth import hash_password
import api.models as m

PRIORITIES = ["critical", "high", "medium", "low"]
STATUSES   = ["open", "in_progress", "escalated", "resolved", "closed"]
CATEGORIES = ["hardware", "software", "network", "access", "performance", "security", "other"]
SOURCES    = ["manual", "auto", "escalation"]

TEAMS = ["network.team", "sysadmin", "helpdesk", "security", "devops", "field.support"]

USERS = [
    {"username": "admin",        "full_name": "Admin User",       "password": "admin123",   "role": "admin",  "team": None},
    {"username": "alice.jones",  "full_name": "Alice Jones",      "password": "pass123",    "role": "agent",  "team": "network.team"},
    {"username": "bob.smith",    "full_name": "Bob Smith",        "password": "pass123",    "role": "agent",  "team": "sysadmin"},
    {"username": "carol.white",  "full_name": "Carol White",      "password": "pass123",    "role": "agent",  "team": "helpdesk"},
    {"username": "dave.sec",     "full_name": "Dave Security",    "password": "pass123",    "role": "agent",  "team": "security"},
    {"username": "eve.devops",   "full_name": "Eve DevOps",       "password": "pass123",    "role": "agent",  "team": "devops"},
    {"username": "frank.field",  "full_name": "Frank Field",      "password": "pass123",    "role": "agent",  "team": "field.support"},
]


def wait_for_db(retries=15, delay=5):
    print("⏳ Waiting for SQL Server to be ready...")
    for attempt in range(1, retries + 1):
        if test_connection():
            print("✅ SQL Server is ready.")
            return True
        print(f"   Attempt {attempt}/{retries} — retrying in {delay}s...")
        time.sleep(delay)
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
        _seed(m.Team,           TEAMS)

        # Seed users
        existing_users = {u.username for u in db.query(m.User).all()}
        teams_map = {t.name: t.id for t in db.query(m.Team).all()}

        for u in USERS:
            if u["username"] not in existing_users:
                db.add(m.User(
                    username        = u["username"],
                    full_name       = u["full_name"],
                    hashed_password = hash_password(u["password"]),
                    role            = u["role"],
                    team_id         = teams_map.get(u["team"]) if u["team"] else None,
                ))
        db.commit()

        print("✅ Lookup tables, teams and users seeded.")
        print("\n👤 Demo accounts:")
        for u in USERS:
            print(f"   {u['username']:20} password: {u['password']:10} role: {u['role']:6} team: {u['team'] or 'all'}")
    finally:
        db.close()


def run_migrations():
    if not wait_for_db():
        sys.exit(1)
    print("\n📦 Creating database if needed...")
    create_database_if_not_exists()
    print("\n📋 Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created.")
    print("\n🔧 Seeding lookup tables, teams and users...")
    seed_lookup_tables()
    print("\n🎉 Migration complete! You can now run: python db/seed.py")


if __name__ == "__main__":
    run_migrations()
