from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import models
from .database import engine
from .routers import auth as auth_router
from .routers import groups as groups_router
from .routers import documents as documents_router
from .routers import admin as admin_router
from .routers import traces as traces_router
from .rag import retrieval

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vehicle Document RAG API")

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


@app.get("/")
def read_root():
    return {"message": "Vehicle Document RAG API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Placeholder for future routers
# app.include_router(auth.router)
# app.include_router(documents.router)
