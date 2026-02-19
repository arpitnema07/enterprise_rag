"""
PostgreSQL migration script — ensures all tables and columns exist.
Uses SQLAlchemy create_all for initial setup, then adds any missing columns.
Safe to run multiple times (idempotent).
"""

import os
from sqlalchemy import create_engine, text, inspect

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://vecvrag:vecvrag_pg_secret@localhost:5432/vecvrag"
)

NEW_COLUMNS = {
    "documents": [
        ("object_key", "TEXT"),
        ("processing_status", "TEXT DEFAULT 'done'"),
        ("processing_error", "TEXT"),
        ("task_id", "TEXT"),
        ("chunk_count", "INTEGER"),
        ("page_count", "INTEGER"),
    ],
}


def migrate():
    engine = create_engine(DATABASE_URL)

    # First, create all tables from models
    from backend.models import Base

    Base.metadata.create_all(bind=engine)
    print("Tables created/verified.")

    # Then, add any missing columns
    inspector = inspect(engine)
    with engine.connect() as conn:
        for table_name, columns in NEW_COLUMNS.items():
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                        )
                    )
                    print(f"  Added column: {table_name}.{col_name} ({col_type})")
            conn.commit()

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
