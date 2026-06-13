import os
import logging
from urllib.parse import quote_plus
from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import sessionmaker, declarative_base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

raw_url = os.getenv("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL not set")

# 1. Strip whitespace
url_str = raw_url.strip()

# 2. Fix the driver prefix
if url_str.startswith("postgres://"):
    url_str = url_str.replace("postgres://", "postgresql+psycopg2://", 1)
elif not url_str.startswith("postgresql+psycopg2://"):
    url_str = url_str.replace("postgresql://", "postgresql+psycopg2://", 1)

# 3. Use SQLAlchemy's robust URL parser
try:
    url_obj = make_url(url_str)

    # 4. Critical: Ensure the password is URL-encoded
    # (Fixes issues where passwords contain special characters like '@' or ':')
    if url_obj.password:
        url_obj = url_obj.set(password=quote_plus(url_obj.password))

    logger.info(f"Connecting to: {url_obj.host}")
except Exception as e:
    logger.error(f"Failed to parse URL: {e}")
    raise

# Engine configuration
engine = create_engine(
    url_obj,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    import models
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
