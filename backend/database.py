from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# PostgreSQL connection — reads from DATABASE_URL env var
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://vecvrag:vecvrag_pg_secret@SRPTH1IDMQFS02.vecvnet.com:5432/vecvrag",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
