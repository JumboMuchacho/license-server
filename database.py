import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Get DATABASE_URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback to local SQLite for development
if DATABASE_URL is None:
    DATABASE_URL = "sqlite:///./licenses.db"  # local fallback

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()
