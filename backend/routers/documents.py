from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import shutil
import os
import hashlib
from .. import models, schemas, auth, database
from ..rag import pipeline as rag_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


@router.post("/upload", response_model=Dict[str, Any])
async def upload_document(
    group_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    # Check if user belongs to the group
    user_group = (
        db.query(models.UserGroup)
        .filter(
            models.UserGroup.user_id == current_user.id,
            models.UserGroup.group_id == group_id,
        )
        .first()
    )

    if not user_group:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    # Save file locally
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Calculate file hash
    file_hash = calculate_file_hash(file_path)

    # Check for duplicate in same group
    existing_doc = (
        db.query(models.Document)
        .filter(
            models.Document.file_hash == file_hash, models.Document.group_id == group_id
        )
        .first()
    )
    if existing_doc:
        # Remove the uploaded file since it's a duplicate
        os.remove(file_path)
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate file. This file already exists as '{existing_doc.filename}'",
        )

    # Process PDF
    try:
        num_chunks = rag_pipeline.process_pdf(
            file_path, group_id, {"filename": file.filename}
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        os.remove(file_path)  # Clean up on failure
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

    # Create Database Entry with hash
    db_doc = models.Document(
        filename=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        group_id=group_id,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return {
        "status": "success",
        "document_id": db_doc.id,
        "chunks_processed": num_chunks,
    }


@router.post("/query")
async def query_documents(
    query_request: schemas.QueryRequest,  # Need to add this to schemas
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    # Get user's groups
    user_groups = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.user_id == current_user.id)
        .all()
    )
    group_ids = [ug.group_id for ug in user_groups]

    if not group_ids:
        return {"answer": "You are not assigned to any groups.", "sources": []}

    # If request specifies a group, verify access
    if query_request.group_id:
        if query_request.group_id not in group_ids:
            raise HTTPException(status_code=403, detail="No access to this group")
        target_groups = [query_request.group_id]
    else:
        target_groups = group_ids

    result = rag_pipeline.generate_answer(
        query_request.query,
        target_groups,
        user_id=current_user.id,
        user_email=current_user.email,
    )

    return result


@router.post("/chat")
async def chat(
    request: schemas.ChatRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Conversational chat endpoint with memory.
    Supports multi-turn conversations with session persistence.
    """
    from ..rag.conversation import ConversationManager

    # Get user's groups
    user_groups = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.user_id == current_user.id)
        .all()
    )
    group_ids = [ug.group_id for ug in user_groups]

    if not group_ids:
        return {
            "answer": "You are not assigned to any groups.",
            "sources": [],
            "session_id": "",
        }

    # If request specifies a group, verify access
    if request.group_id:
        if request.group_id not in group_ids:
            raise HTTPException(status_code=403, detail="No access to this group")
        target_groups = [request.group_id]
    else:
        target_groups = group_ids

    # Create or resume conversation
    try:
        if request.session_id:
            conv_manager = ConversationManager.from_session(
                request.session_id, current_user.id, target_groups
            )
        else:
            conv_manager = ConversationManager(current_user.id, target_groups)
    except Exception:
        # If Redis is unavailable, create a new session
        conv_manager = ConversationManager(current_user.id, target_groups)

    # Get conversation history
    try:
        history = conv_manager.get_history(last_n=5)
    except Exception:
        history = []

    # Generate answer with history and optional filters
    result = rag_pipeline.generate_answer_with_context(
        query=request.message,
        group_ids=target_groups,
        history=history,
        filters=request.filters,
    )

    # Store messages in conversation history
    try:
        conv_manager.add_message("user", request.message)
        conv_manager.add_message("assistant", result["answer"])
    except Exception:
        # Continue even if Redis storage fails
        pass

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "session_id": conv_manager.session_key,
    }
