from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./licenses.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def apply_pending_migrations():
	"""Apply minimal, safe migrations for the local sqlite DB.

	Currently only ensures the `expires_at` column exists on `licenses`.
	"""
	# Use raw sqlite connection to run PRAGMA/ALTER easily
	conn = engine.raw_connection()
	try:
		cur = conn.cursor()
		cur.execute("PRAGMA table_info(licenses)")
		cols = [row[1] for row in cur.fetchall()]
		if 'expires_at' not in cols:
			cur.execute("ALTER TABLE licenses ADD COLUMN expires_at DATETIME")
			conn.commit()
		# add assigned_users column if missing (stores JSON text)
		if 'assigned_users' not in cols:
			cur.execute("ALTER TABLE licenses ADD COLUMN assigned_users TEXT")
			conn.commit()
	finally:
		try:
			cur.close()
		except Exception:
			pass
		conn.close()
