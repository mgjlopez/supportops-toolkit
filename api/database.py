"""
database.py — SQLAlchemy connection setup for SQL Server Developer Edition.
Uses pyodbc + ODBC Driver 18 for SQL Server.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "SupportOpsDB")
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

CONNECTION_STRING = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}"
    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
)

# Connection string to 'master' — used only for connectivity checks and DB creation
MASTER_CONNECTION_STRING = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/master"
    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
)

engine = create_engine(
    CONNECTION_STRING,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """
    Checks connectivity against 'master' so it works even before
    SupportOpsDB has been created by migrate.py.
    """
    try:
        master_engine = create_engine(MASTER_CONNECTION_STRING)
        with master_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        master_engine.dispose()
        return True
    except Exception as e:
        print(f"[DB] Connection failed: {e}")
        return False
