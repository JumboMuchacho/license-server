import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Configure logging for Render deployment debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch URL - prioritize Environment Variables over .env for Render
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# 1. Standardize prefix: Force the specific postgresql+psycopg2 dialect
# 2. Clean the string: Remove any accidental whitespace or hidden characters
url = DATABASE_URL.strip()

if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg2://", 1)
elif not url.startswith("postgresql+psycopg2://"):
    # If it's already postgresql://, upgrade it to the psycopg2 driver
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

logger.info(f"Connecting to database host: {url.split('@')[-1].split(':')[0]}")

# Engine configuration
engine = create_engine(
    url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    """Syncs models to the database."""
    import models
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
