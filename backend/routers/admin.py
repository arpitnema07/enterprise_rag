from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from .. import models, schemas, auth, database
from ..rag import retrieval

router = APIRouter(prefix="/admin", tags=["admin"])

# ==================== DOCUMENTS ====================


@router.get("/documents", response_model=List[schemas.Document])
def get_all_documents(
    group_id: Optional[int] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(models.Document)
    if group_id:
        query = query.filter(models.Document.group_id == group_id)
    return query.all()


@router.get("/groups/{group_id}/documents", response_model=List[schemas.Document])
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
    return documents


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
        print(f"Warning: Failed to delete from Qdrant: {e}")

    # Delete physical file
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            print(f"Warning: Failed to delete file: {e}")

    # Delete from DB
    db.delete(doc)
    db.commit()
    return {"message": f"Document {doc_id} deleted"}


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

    # Delete user's group memberships first
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
    This is useful after updating embedding logic.
    Requires confirm=true to execute.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if not confirm:
        # Return stats about what would be re-indexed
        doc_count = db.query(models.Document).count()
        return {
            "message": "Pass confirm=true to re-index all documents",
            "documents_to_reindex": doc_count,
            "warning": "This will delete all embeddings and re-process all documents",
        }

    # Import here to avoid circular imports
    from ..rag import pipeline as rag_pipeline

    # Get all documents
    documents = db.query(models.Document).all()

    if not documents:
        return {"message": "No documents to re-index", "processed": 0}

    # Recreate the collection (clears all embeddings)
    try:
        retrieval.recreate_collection()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to clear embeddings: {str(e)}"
        )

    # Re-process each document
    success_count = 0
    failed = []

    for doc in documents:
        try:
            if os.path.exists(doc.file_path):
                rag_pipeline.process_pdf(
                    doc.file_path, doc.group_id, {"filename": doc.filename}
                )
                success_count += 1
            else:
                failed.append(
                    {"id": doc.id, "filename": doc.filename, "error": "File not found"}
                )
        except Exception as e:
            failed.append({"id": doc.id, "filename": doc.filename, "error": str(e)})

    return {
        "message": "Re-indexing complete",
        "processed": success_count,
        "failed": len(failed),
        "failures": failed[:10] if failed else [],  # Return first 10 failures
    }


# ==================== LLM STATUS ====================


@router.get("/llm-status")
def get_llm_status(
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get current LLM provider status and configuration.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ..rag.generation import get_current_provider

    return get_current_provider()
