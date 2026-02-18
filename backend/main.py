from dotenv import load_dotenv
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env file in the project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configure thread pool for concurrent LLM calls (default asyncio pool is too small)
# This allows up to 10 blocking LLM requests to run concurrently via asyncio.to_thread()
_executor = ThreadPoolExecutor(max_workers=10)
asyncio.get_event_loop().set_default_executor(_executor)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Create tables
models.Base.metadata.create_all(bind=engine)

# Disable redirect_slashes to prevent CORS issues with trailing slash redirects
app = FastAPI(title="Vehicle Document RAG API", redirect_slashes=False)

# Ensure QDrant Collection Exists
try:
    retrieval.ensure_collection()
except Exception as e:
    print(f"WARNING: Failed to ensure Qdrant collection: {e}")

# CORS (Allow all for MVP dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Placeholder for future routers
# app.include_router(auth.router)
# app.include_router(documents.router)
