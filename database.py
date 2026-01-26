import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --------------------------------------------------
# Database URL
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix old postgres:// URLs
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Local fallback (dev only)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./licenses.db"

# --------------------------------------------------
# Engine configuration
# --------------------------------------------------
engine_args = {
    "pool_pre_ping": True,
}

# SQLite (local development)
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

# Supabase Postgres (Session Pooler / IPv4)
if DATABASE_URL.startswith("postgresql"):
    engine_args["connect_args"] = {"sslmode": "require"}
    engine_args["pool_recycle"] = 300  # 🔑 important for poolers

engine = create_engine(DATABASE_URL, **engine_args)

# --------------------------------------------------
# Session & Base
# --------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# --------------------------------------------------
# Local-only migrations (SQLite)
# --------------------------------------------------
def apply_pending_migrations():
    # Never run migrations against Supabase
    if not DATABASE_URL.startswith("sqlite"):
        return

    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(licenses)")
        cols = [row[1] for row in cur.fetchall()]

        if "expires_at" not in cols:
            cur.execute("ALTER TABLE licenses ADD COLUMN expires_at DATETIME")

        if "assigned_users" not in cols:
            cur.execute("ALTER TABLE licenses ADD COLUMN assigned_users TEXT")

        conn.commit()
    finally:
        conn.close()
