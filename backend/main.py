from dotenv import load_dotenv
from pathlib import Path
import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env file in the project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configure thread pool for concurrent LLM calls (default asyncio pool is too small)
_executor = ThreadPoolExecutor(max_workers=10)
asyncio.get_event_loop().set_default_executor(_executor)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from . import models
from .database import engine
from .routers import auth as auth_router
from .routers import groups as groups_router
from .routers import documents as documents_router
from .routers import admin as admin_router
from .routers import traces as traces_router
from .routers import websocket as websocket_router
from .routers import conversations as conversations_router
from .routers import models as models_router
from .rag import retrieval

logger = logging.getLogger(__name__)

# Create tables
models.Base.metadata.create_all(bind=engine)

# Rate limiter — global instance
limiter = Limiter(key_func=get_remote_address)

# Disable redirect_slashes to prevent CORS issues with trailing slash redirects
app = FastAPI(title="Vehicle Document RAG API", redirect_slashes=False)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Ensure QDrant Collection Exists
try:
    retrieval.ensure_collection()
except Exception as e:
    print(f"WARNING: Failed to ensure Qdrant collection: {e}")

# Ensure ClickHouse Events Table Exists
try:
    from .services.clickhouse_client import ensure_table_exists

    ensure_table_exists()
except Exception as e:
    print(f"WARNING: Failed to ensure ClickHouse events table: {e}")

# CORS — Locked down to known frontend origins
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://it54376:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


# Global exception handler — never expose tracebacks to the client
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again later."
        },
    )


app.include_router(auth_router.router)
app.include_router(groups_router.router)
app.include_router(documents_router.router)
app.include_router(admin_router.router)
app.include_router(traces_router.router)
app.include_router(websocket_router.router)
app.include_router(conversations_router.router)
app.include_router(models_router.router)


@app.get("/")
def read_root():
    return {"message": "Vehicle Document RAG API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
