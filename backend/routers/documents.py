from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, Any
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
    from ..rag.realtime_logger import log_request, log_response
    import time

    start_time = time.time()

    # Log incoming request
    log_request(
        query_request.query, user_id=current_user.id, user_email=current_user.email
    )

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

    # Log response
    total_time = (time.time() - start_time) * 1000
    log_response(
        response_length=len(result.get("answer", "")),
        total_duration_ms=total_time,
        user_id=current_user.id,
    )

    return result


@router.post("/chat")
async def chat(
    request: schemas.ChatRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Conversational chat endpoint with agentic routing.
    Uses intent classification for smart response routing.
    Persists conversations to database with Redis cache for recent messages.
    """
    import json
    import asyncio
    from ..rag.conversation import ConversationManager
    from ..rag.agentic_router import run_agentic_query

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
            "conversation_id": None,
            "intent": "error",
        }

    # If request specifies a group, verify access and get prompt_type
    prompt_type = "technical"  # default
    target_group_id = None

    if request.group_id:
        if request.group_id not in group_ids:
            raise HTTPException(status_code=403, detail="No access to this group")
        target_group_id = request.group_id
        target_groups = [request.group_id]

        # Get group's prompt type
        group = (
            db.query(models.Group).filter(models.Group.id == request.group_id).first()
        )
        if group and group.prompt_type:
            prompt_type = group.prompt_type
    else:
        target_groups = group_ids

    # Handle persistent conversation (database)
    db_conversation = None
    is_new_conversation = False

    if request.conversation_id:
        # Load existing conversation
        db_conversation = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.id == request.conversation_id,
                models.Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not db_conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Create new conversation
        is_new_conversation = True
        # Generate title from first message (truncate to 50 chars)
        title = (
            request.message[:50] + "..."
            if len(request.message) > 50
            else request.message
        )
        db_conversation = models.Conversation(
            user_id=current_user.id,
            title=title,
            group_id=target_group_id,
        )
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)

    # Create or resume Redis session for fast access to recent messages
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

    # Get conversation history from Redis (fast cache) or fallback to database
    try:
        history = conv_manager.get_history(last_n=5)
    except Exception:
        history = []

    # If Redis history is empty but we have a conversation, load from database
    if not history and db_conversation and not is_new_conversation:
        try:
            db_messages = (
                db.query(models.ChatMessage)
                .filter(models.ChatMessage.conversation_id == db_conversation.id)
                .order_by(models.ChatMessage.created_at.desc())
                .limit(10)
                .all()
            )
            # Reverse to get chronological order
            db_messages.reverse()
            history = [
                {"role": msg.role, "content": msg.content} for msg in db_messages
            ]
        except Exception:
            history = []

    # Run through agentic router in a background thread to avoid blocking the event loop
    result = await asyncio.to_thread(
        run_agentic_query,
        query=request.message,
        group_ids=target_groups,
        user_id=current_user.id,
        session_id=conv_manager.session_key,
        group_id=target_group_id,
        prompt_type=prompt_type,
        history=history,
        model_provider=request.model_provider,
        model_name=request.model_name,
    )

    # Store messages in Redis (cache) for quick access
    try:
        conv_manager.add_message("user", request.message)
        conv_manager.add_message("assistant", result["answer"])
    except Exception:
        # Continue even if Redis storage fails
        pass

    # Persist messages to database
    try:
        # Save user message
        user_msg = models.ChatMessage(
            conversation_id=db_conversation.id,
            role="user",
            content=request.message,
        )
        db.add(user_msg)

        # Save assistant message with sources
        sources_json = json.dumps(result["sources"]) if result.get("sources") else None
        assistant_msg = models.ChatMessage(
            conversation_id=db_conversation.id,
            role="assistant",
            content=result["answer"],
            sources_json=sources_json,
            intent=result.get("intent"),
        )
        db.add(assistant_msg)
        db.commit()
    except Exception as e:
        # Log error but don't fail the request
        print(f"Error saving messages to database: {e}")

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "session_id": conv_manager.session_key,
        "conversation_id": db_conversation.id,
        "intent": result.get("intent"),
        "latency": result.get("latency"),
    }
