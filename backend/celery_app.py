"""
Celery application configuration.
Uses Redis as the message broker and result backend.
"""

import os
from dotenv import load_dotenv
from celery import Celery

# Load .env so Celery worker picks up config when running standalone
load_dotenv()

# Redis connection for Celery
REDIS_URL = os.getenv("CELERY_BROKER_URL", "")

celery_app = Celery(
    "vecvrag",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks.document_tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,  # Acknowledge after completion (crash-safe)
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_reject_on_worker_lost=True,
    # Result expiration
    result_expires=3600,  # 1 hour
    # Task time limits
    task_soft_time_limit=600,  # 10 minutes soft limit
    task_time_limit=900,  # 15 minutes hard limit
)
