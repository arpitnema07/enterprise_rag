import os
import logging
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from .. import models, schemas, auth, database
from ..rag import retrieval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== STATS ====================


@router.get("/stats")
def get_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Dashboard stats: counts for docs, chunks, users, groups, storage."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    doc_count = db.query(models.Document).count()
    total_chunks = db.query(func.sum(models.Document.chunk_count)).scalar() or 0
    user_count = db.query(models.User).count()
    group_count = db.query(models.Group).count()

    # Processing queue stats
    pending = (
        db.query(models.Document)
        .filter(models.Document.processing_status == "pending")
        .count()
    )
    processing = (
        db.query(models.Document)
        .filter(models.Document.processing_status == "processing")
        .count()
    )
    failed = (
        db.query(models.Document)
        .filter(models.Document.processing_status == "failed")
        .count()
    )

    # MinIO storage stats
    storage = {}
    try:
        from ..services import minio_client

        storage = minio_client.get_bucket_stats()
    except Exception as e:
        logger.warning(f"Failed to get MinIO stats: {e}")

    return {
        "documents": doc_count,
        "total_chunks": total_chunks,
        "users": user_count,
        "groups": group_count,
        "queue": {
            "pending": pending,
            "processing": processing,
            "failed": failed,
        },
        "storage": storage,
    }


# ==================== SERVICE HEALTH ====================


@router.get("/service-health")
def get_service_health(
    current_user: models.User = Depends(auth.get_current_user),
):
    """Check connectivity to all infrastructure services."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    health = {}

    # Qdrant
    try:
        info = retrieval.get_collection_info()
        health["qdrant"] = {
            "status": "ok",
            "points": info.points_count,
            "collection": retrieval.COLLECTION_NAME,
        }
    except Exception as e:
        health["qdrant"] = {"status": "error", "detail": str(e)[:200]}

    # MinIO
    try:
        from ..services import minio_client

        stats = minio_client.get_bucket_stats()
        health["minio"] = {"status": "ok", **stats}
    except Exception as e:
        health["minio"] = {"status": "error", "detail": str(e)[:200]}

    # ClickHouse
    try:
        from ..services import clickhouse_client

        ch_ok = clickhouse_client.health_check()
        health["clickhouse"] = {"status": "ok" if ch_ok else "error"}
    except Exception as e:
        health["clickhouse"] = {"status": "error", "detail": str(e)[:200]}

    # Redis
    try:
        import redis

        redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
        r = redis.from_url(redis_url)
        r.ping()
        health["redis"] = {"status": "ok"}
    except Exception as e:
        health["redis"] = {"status": "error", "detail": str(e)[:200]}

    # Ollama
    try:
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = requests.get(f"{ollama_url}/api/tags", timeout=3)
        model_count = len(resp.json().get("models", []))
        health["ollama"] = {"status": "ok", "models": model_count}
    except Exception as e:
        health["ollama"] = {"status": "error", "detail": str(e)[:200]}

    # PostgreSQL
    try:
        db = next(database.get_db())
        db.execute(func.now())
        health["postgres"] = {"status": "ok"}
    except Exception as e:
        health["postgres"] = {"status": "error", "detail": str(e)[:200]}

    return health


# ==================== DOCUMENTS ====================


@router.get("/documents")
def get_all_documents(
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """List all documents with optional group and status filters."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(models.Document)
    if group_id:
        query = query.filter(models.Document.group_id == group_id)
    if status:
        query = query.filter(models.Document.processing_status == status)

    docs = query.order_by(models.Document.upload_date.desc()).all()

    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_path": doc.file_path,
            "group_id": doc.group_id,
            "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
            "object_key": doc.object_key,
            "processing_status": doc.processing_status,
            "processing_error": doc.processing_error,
            "chunk_count": doc.chunk_count,
            "page_count": doc.page_count,
            "file_hash": doc.file_hash,
        }
        for doc in docs
    ]


@router.get("/groups/{group_id}/documents")
def get_group_documents(
    group_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    documents = (
        db.query(models.Document).filter(models.Document.group_id == group_id).all()
    )
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_path": doc.file_path,
            "group_id": doc.group_id,
            "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
            "processing_status": doc.processing_status,
            "chunk_count": doc.chunk_count,
        }
        for doc in documents
    ]


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Qdrant
    try:
        retrieval.delete_by_file_path(doc.file_path)
    except Exception as e:
        logger.warning(f"Failed to delete from Qdrant: {e}")

    # Delete from MinIO
    if doc.object_key:
        try:
            from ..services import minio_client

            minio_client.delete_file(doc.object_key)
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")

    # Delete physical file
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file: {e}")

    db.delete(doc)
    db.commit()
    return {"message": f"Document {doc_id} deleted"}


# Retry failed document processing
@router.post("/documents/{doc_id}/retry")
def retry_document(
    doc_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Re-dispatch a failed document for processing."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.processing_status not in ("failed", "done"):
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed or completed documents, current status: {doc.processing_status}",
        )

    doc.processing_status = "pending"
    doc.processing_error = None
    db.commit()

    try:
        from backend.tasks.document_tasks import process_document_task

        task = process_document_task.delay(doc.id)
        doc.task_id = task.id
        db.commit()
    except Exception as e:
        logger.warning(f"Celery dispatch failed: {e}")
        doc.processing_status = "failed"
        doc.processing_error = "Celery worker not available"
        db.commit()
        raise HTTPException(status_code=503, detail="Background worker not available")

    return {
        "message": f"Document {doc_id} queued for reprocessing",
        "task_id": doc.task_id,
    }


# ==================== USERS ====================


@router.get("/users", response_model=List[schemas.User])
def list_all_users(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    return db.query(models.User).all()


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(models.UserGroup).filter(models.UserGroup.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"message": f"User {user_id} deleted"}


@router.put("/users/{user_id}/toggle-admin")
def toggle_admin(
    user_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Cannot change your own admin status"
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_admin = not user.is_admin
    db.commit()
    return {"message": f"User {user_id} admin status: {user.is_admin}"}


# ==================== GROUP USERS ====================


@router.get("/groups/{group_id}/users", response_model=List[schemas.User])
def get_group_users(
    group_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    user_groups = (
        db.query(models.UserGroup).filter(models.UserGroup.group_id == group_id).all()
    )
    user_ids = [ug.user_id for ug in user_groups]
    users = db.query(models.User).filter(models.User.id.in_(user_ids)).all()
    return users


@router.post("/groups/{group_id}/assign-user")
def assign_user_to_group(
    group_id: int,
    user_email: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(models.User).filter(models.User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(models.UserGroup)
        .filter(
            models.UserGroup.user_id == user.id, models.UserGroup.group_id == group_id
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="User already in group")

    db_user_group = models.UserGroup(user_id=user.id, group_id=group_id, role="member")
    db.add(db_user_group)
    db.commit()

    return {"message": f"User {user_email} assigned to group {group_id}"}


@router.delete("/groups/{group_id}/users/{user_id}")
def remove_user_from_group(
    group_id: int,
    user_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    user_group = (
        db.query(models.UserGroup)
        .filter(
            models.UserGroup.user_id == user_id, models.UserGroup.group_id == group_id
        )
        .first()
    )

    if not user_group:
        raise HTTPException(status_code=404, detail="User not in group")

    db.delete(user_group)
    db.commit()
    return {"message": f"User {user_id} removed from group {group_id}"}


# ==================== RE-INDEXING ====================


@router.post("/reindex")
def reindex_all_documents(
    confirm: bool = False,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Clear all embeddings and re-process all documents.
    Requires confirm=true to execute.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if not confirm:
        doc_count = db.query(models.Document).count()
        return {
            "message": "Pass confirm=true to re-index all documents",
            "documents_to_reindex": doc_count,
            "warning": "This will delete all embeddings and re-process all documents",
        }

    from ..rag import pipeline as rag_pipeline

    documents = db.query(models.Document).all()

    if not documents:
        return {"message": "No documents to re-index", "processed": 0}

    try:
        retrieval.recreate_collection()
    except Exception as e:
        logger.error(f"Failed to clear embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to clear embeddings.")

    success_count = 0
    failed = []

    for doc in documents:
        try:
            if doc.file_path and os.path.exists(doc.file_path):
                rag_pipeline.process_pdf(
                    doc.file_path, doc.group_id, {"filename": doc.filename}
                )
                success_count += 1
            elif doc.object_key:
                # Try to reprocess via Celery
                doc.processing_status = "pending"
                db.commit()
                try:
                    from backend.tasks.document_tasks import process_document_task

                    process_document_task.delay(doc.id)
                    success_count += 1
                except Exception:
                    failed.append(
                        {
                            "id": doc.id,
                            "filename": doc.filename,
                            "error": "Celery unavailable",
                        }
                    )
            else:
                failed.append(
                    {"id": doc.id, "filename": doc.filename, "error": "No file source"}
                )
        except Exception as e:
            failed.append(
                {"id": doc.id, "filename": doc.filename, "error": str(e)[:200]}
            )

    return {
        "message": "Re-indexing complete",
        "processed": success_count,
        "failed": len(failed),
        "failures": failed[:10] if failed else [],
    }


# ==================== LLM STATUS ====================


@router.get("/llm-status")
def get_llm_status(
    current_user: models.User = Depends(auth.get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ..rag.generation import get_current_provider

    return get_current_provider()
