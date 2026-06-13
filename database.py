import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the raw URL directly from your Environment Variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

# Engine configuration - SQLAlchemy handles the string natively and safely
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,  # Crucial for cloud databases to detect dropped connections
    connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    """Initializes database tables. Import models here to prevent circular imports."""
    import models
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for FastAPI to manage DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
