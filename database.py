import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the raw string
raw_url = os.getenv("DATABASE_URL", "").strip()

# We need to manually split this to avoid the regex parser
# Format: postgresql://user:pass@host:port/db #pragma: allowlist secret
try:
    # 1. Remove the protocol prefix
    clean_url = raw_url.replace("postgresql+psycopg2://", "").replace("postgresql://", "").replace("postgres://", "")

    # 2. Extract credentials and host info
    credentials, host_info = clean_url.split("@")
    username, password = credentials.split(":", 1)
    host, rest = host_info.split(":", 1)
    port, dbname = rest.split("/", 1)

    # 3. Create the URL object manually
    url_obj = URL.create(
        drivername="postgresql+psycopg2",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=dbname
    )
    logger.info("URL object constructed successfully.")
except Exception as e:
    logger.error(f"Manual parsing failed: {e}")
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
