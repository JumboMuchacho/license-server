from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./licenses.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def apply_pending_migrations():
    """
    Apply minimal safe migrations for sqlite.
    """
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
        cur.close()
        conn.close()
