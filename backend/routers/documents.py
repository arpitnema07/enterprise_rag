from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import shutil
import os
import re
import hashlib
import tempfile
import json
import asyncio
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from .. import models, schemas, auth, database
from ..rag import pipeline as rag_pipeline
from ..services import minio_client

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- File Upload Security ----

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
    "application/vnd.ms-powerpoint",  # ppt
}
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", ".pdf,.ppt,.pptx").split(","))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    """Sanitize filename — only allow safe characters."""
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r"[^\w\-.]", "_", name)
    safe_name = safe_name.lstrip(".")
    if not safe_name:
        safe_name = "document"
    return safe_name + ext.lower()


def validate_upload(file: UploadFile) -> None:
    """Validate file type before processing."""
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type '{file.content_type}' not allowed. Upload PDF or PPTX files.",
        )


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


# ---- Endpoints ----


@router.post("/upload", response_model=Dict[str, Any])
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    group_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    # Validate file type
    validate_upload(file)

    # Check group membership
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

    safe_filename = sanitize_filename(file.filename)
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, safe_filename)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Check file size
        if os.path.getsize(temp_path) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.",
            )

        file_hash = calculate_file_hash(temp_path)

        # Check duplicate
        existing_doc = (
            db.query(models.Document)
            .filter(
                models.Document.file_hash == file_hash,
                models.Document.group_id == group_id,
            )
            .first()
        )
        if existing_doc:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate file. Already exists as '{existing_doc.filename}'",
            )

        # Upload to MinIO
        object_key = f"group_{group_id}/{file_hash}_{safe_filename}"
        try:
            minio_client.upload_file(
                temp_path,
                object_key,
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception as e:
            logger.error(f"MinIO upload failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Failed to upload file to storage."
            )

        # Local copy for processing
        local_path = os.path.join(UPLOAD_DIR, safe_filename)
        shutil.copy2(temp_path, local_path)

        # Process PDF
        try:
            num_chunks = rag_pipeline.process_pdf(
                local_path, group_id, {"filename": safe_filename}
            )
        except Exception as e:
            logger.error(
                f"PDF processing failed for {safe_filename}: {e}", exc_info=True
            )
            try:
                minio_client.delete_file(object_key)
            except Exception:
                pass
            if os.path.exists(local_path):
                os.remove(local_path)
            raise HTTPException(
                status_code=500, detail="Error processing file. Please try again."
            )

        db_doc = models.Document(
            filename=safe_filename,
            file_path=local_path,
            file_hash=file_hash,
            group_id=group_id,
            object_key=object_key,
            processing_status="done",
            chunk_count=num_chunks,
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        return {
            "status": "success",
            "document_id": db_doc.id,
            "chunks_processed": num_chunks,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/query")
@limiter.limit("30/minute")
async def query_documents(
    request: Request,
    query_request: schemas.QueryRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    from ..rag.observability import log_request, log_response
    import time

    start_time = time.time()

    log_request(
        query_request.query, user_id=current_user.id, user_email=current_user.email
    )

    user_groups = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.user_id == current_user.id)
        .all()
    )
    group_ids = [ug.group_id for ug in user_groups]

    if not group_ids:
        return {"answer": "You are not assigned to any groups.", "sources": []}

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

    total_time = (time.time() - start_time) * 1000
    log_response(
        response_length=len(result.get("answer", "")),
        total_duration_ms=total_time,
        user_id=current_user.id,
    )

    return result


@router.post("/chat")
@limiter.limit("30/minute")
async def chat(
    http_request: Request,
    request: schemas.ChatRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Conversational chat endpoint with agentic routing.
    Uses intent classification for smart response routing.
    Persists conversations to database with Redis cache for recent messages.
    """
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

    # Group access and prompt type
    prompt_type = "technical"
    target_group_id = None

    if request.group_id:
        if request.group_id not in group_ids:
            raise HTTPException(status_code=403, detail="No access to this group")
        target_group_id = request.group_id
        target_groups = [request.group_id]

        group = (
            db.query(models.Group).filter(models.Group.id == request.group_id).first()
        )
        if group and group.prompt_type:
            prompt_type = group.prompt_type
    else:
        target_groups = group_ids

    # Handle persistent conversation
    db_conversation = None
    is_new_conversation = False

    if request.conversation_id:
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
        is_new_conversation = True
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

    # Redis session
    try:
        if request.session_id:
            conv_manager = ConversationManager.from_session(
                request.session_id, current_user.id, target_groups
            )
        else:
            conv_manager = ConversationManager(current_user.id, target_groups)
    except Exception:
        conv_manager = ConversationManager(current_user.id, target_groups)

    # Get history
    try:
        history = conv_manager.get_history(last_n=5)
    except Exception:
        history = []

    # DB fallback for history
    if not history and db_conversation and not is_new_conversation:
        try:
            db_messages = (
                db.query(models.ChatMessage)
                .filter(models.ChatMessage.conversation_id == db_conversation.id)
                .order_by(models.ChatMessage.created_at.desc())
                .limit(10)
                .all()
            )
            db_messages.reverse()
            history = [
                {"role": msg.role, "content": msg.content} for msg in db_messages
            ]
        except Exception:
            history = []

    # Run agentic query
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

    # Cache in Redis
    try:
        conv_manager.add_message("user", request.message)
        conv_manager.add_message("assistant", result["answer"])
    except Exception:
        pass

    # Persist to DB
    try:
        user_msg = models.ChatMessage(
            conversation_id=db_conversation.id,
            role="user",
            content=request.message,
        )
        db.add(user_msg)

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
        logger.error(f"Error saving messages to database: {e}", exc_info=True)

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "session_id": conv_manager.session_key,
        "conversation_id": db_conversation.id,
        "intent": result.get("intent"),
        "latency": result.get("latency"),
    }
