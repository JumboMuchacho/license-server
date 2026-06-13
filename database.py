import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the raw URL from Environment Variables
# Ensure this URL uses port 6543 (Supabase Transaction Pooler)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

# Configure connection arguments to handle SSL without requiring a local root certificate file
# This resolves the "Could not open SSL root certificate file" error
connect_args = {
    "sslmode": "require"
}

# Engine configuration
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,            # Reduced for free-tier database limits
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,     # Crucial: checks connection health before use
    connect_args=connect_args
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    """Initializes database tables. Import models here to prevent circular imports."""
    try:
        import models
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # We don't necessarily raise here to allow the app to boot,
        # but handle the error based on your preference.

def get_db():
    """Dependency for FastAPI to manage DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
