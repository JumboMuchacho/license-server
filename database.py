import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

# Use connect_args for dialect-specific requirements
connect_args = {"sslmode": "require"}

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool, # Explicitly stating pool type
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,  # Crucial for stability
    connect_args=connect_args
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
