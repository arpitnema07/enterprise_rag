from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
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

        # Create DB record with pending status
        db_doc = models.Document(
            filename=safe_filename,
            file_path="",
            file_hash=file_hash,
            group_id=group_id,
            object_key=object_key,
            processing_status="pending",
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        # Dispatch Celery task for background processing
        try:
            from backend.tasks.document_tasks import process_document_task

            task = process_document_task.delay(db_doc.id)
            db_doc.task_id = task.id
            db.commit()
        except Exception as e:
            # Celery not available — fall back to synchronous processing
            logger.warning(f"Celery dispatch failed, processing synchronously: {e}")
            try:
                local_path = os.path.join(UPLOAD_DIR, safe_filename)
                shutil.copy2(temp_path, local_path)
                num_chunks = rag_pipeline.process_document(
                    local_path, group_id, {"filename": safe_filename}
                )
                db_doc.file_path = local_path
                db_doc.processing_status = "done"
                db_doc.chunk_count = num_chunks
                db.commit()
            except Exception as proc_err:
                logger.error(f"Sync fallback failed: {proc_err}", exc_info=True)
                db_doc.processing_status = "failed"
                db_doc.processing_error = str(proc_err)[:500]
                db.commit()

        return {
            "status": "accepted",
            "document_id": db_doc.id,
            "processing_status": db_doc.processing_status,
            "task_id": db_doc.task_id,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/{doc_id}/status")
async def get_document_status(
    doc_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Poll document processing status."""
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify user has access (belongs to same group)
    user_group = (
        db.query(models.UserGroup)
        .filter(
            models.UserGroup.user_id == current_user.id,
            models.UserGroup.group_id == doc.group_id,
        )
        .first()
    )
    if not user_group and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No access to this document")

    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "processing_status": doc.processing_status,
        "chunk_count": doc.chunk_count,
        "processing_error": doc.processing_error,
        "task_id": doc.task_id,
    }


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
    request: Request,
    chat_request: schemas.ChatRequest,
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

    if chat_request.group_id:
        if chat_request.group_id not in group_ids:
            raise HTTPException(status_code=403, detail="No access to this group")
        target_group_id = chat_request.group_id
        target_groups = [chat_request.group_id]

        group = (
            db.query(models.Group)
            .filter(models.Group.id == chat_request.group_id)
            .first()
        )
        if group and group.prompt_type:
            prompt_type = group.prompt_type
    else:
        target_groups = group_ids

    # Handle persistent conversation
    db_conversation = None
    is_new_conversation = False

    if chat_request.conversation_id:
        db_conversation = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.id == chat_request.conversation_id,
                models.Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not db_conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        is_new_conversation = True
        title = (
            chat_request.message[:50] + "..."
            if len(chat_request.message) > 50
            else chat_request.message
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
        if chat_request.session_id:
            conv_manager = ConversationManager.from_session(
                chat_request.session_id, current_user.id, target_groups
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

    # Temporary debug: bypass history to test if past refusals poison the LLM
    history = []

    # If the UI sends empty strings for model, default to nvidia to ensure quality
    mod_provider = (
        chat_request.model_provider if chat_request.model_provider else "nvidia"
    )
    mod_name = (
        chat_request.model_name
        if chat_request.model_name
        else "meta/llama-3.1-405b-instruct"
    )

    # Run agentic query
    result = await asyncio.to_thread(
        run_agentic_query,
        query=chat_request.message,
        group_ids=target_groups,
        user_id=current_user.id,
        session_id=conv_manager.session_key,
        group_id=target_group_id,
        prompt_type=prompt_type,
        history=history,
        model_provider=mod_provider,
        model_name=mod_name,
    )

    # Cache in Redis
    try:
        conv_manager.add_message("user", chat_request.message)
        conv_manager.add_message("assistant", result["answer"])
    except Exception:
        pass

    # Persist to DB
    try:
        user_msg = models.ChatMessage(
            conversation_id=db_conversation.id,
            role="user",
            content=chat_request.message,
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


@router.post("/chat-stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    chat_request: schemas.ChatRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Yields tokens as they are generated, then a final event with sources/metadata.
    """
    import queue
    import threading
    from ..rag.conversation import ConversationManager
    from ..rag.agentic_router import run_agentic_query

    # Group validation (same as sync chat)
    user_groups = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.user_id == current_user.id)
        .all()
    )
    group_ids = [ug.group_id for ug in user_groups]

    if not group_ids:

        async def err_stream():
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'You are not assigned to any groups.'})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        return StreamingResponse(err_stream(), media_type="text/event-stream")

    print(
        f"DEBUG: UI Requested Model Provider: {chat_request.model_provider} - Model Name: {chat_request.model_name}"
    )

    prompt_type = "technical"
    target_group_id = None

    if chat_request.group_id:
        if chat_request.group_id not in group_ids:
            raise HTTPException(status_code=403, detail="No access to this group")
        target_group_id = chat_request.group_id
        target_groups = [chat_request.group_id]

        group = (
            db.query(models.Group)
            .filter(models.Group.id == chat_request.group_id)
            .first()
        )
        if group and group.prompt_type:
            prompt_type = group.prompt_type
    else:
        target_groups = group_ids

    # Conversation tracking
    db_conversation = None
    is_new_conversation = False

    if chat_request.conversation_id:
        db_conversation = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.id == chat_request.conversation_id,
                models.Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not db_conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        is_new_conversation = True
        title = (
            chat_request.message[:50] + "..."
            if len(chat_request.message) > 50
            else chat_request.message
        )
        db_conversation = models.Conversation(
            user_id=current_user.id, title=title, group_id=target_group_id
        )
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)

    # Cache/Session logic
    try:
        if chat_request.session_id:
            conv_manager = ConversationManager.from_session(
                chat_request.session_id, current_user.id, target_groups
            )
        else:
            conv_manager = ConversationManager(current_user.id, target_groups)
    except Exception:
        conv_manager = ConversationManager(current_user.id, target_groups)

    try:
        history = conv_manager.get_history(last_n=5)
    except Exception:
        history = []

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

    # Temporary debug: bypass history to test if past refusals poison the LLM
    history = []

    stream_q = queue.Queue()
    result_container = {}

    print(
        f"DEBUG: UI Requested Model Provider: {chat_request.model_provider} - Model Name: {chat_request.model_name}"
    )

    # Force NVIDIA if the UI didn't explicitly request a model
    mod_provider = (
        chat_request.model_provider if chat_request.model_provider else "nvidia"
    )
    mod_name = (
        chat_request.model_name
        if chat_request.model_name
        else "meta/llama-3.1-405b-instruct"
    )

    def background_task():
        try:
            res = run_agentic_query(
                query=chat_request.message,
                group_ids=target_groups,
                user_id=current_user.id,
                session_id=conv_manager.session_key,
                group_id=target_group_id,
                prompt_type=prompt_type,
                history=history,
                model_provider=mod_provider,
                model_name=mod_name,
                stream_queue=stream_q,
            )
            result_container["result"] = res
        except Exception as e:
            logger.error(f"Error in background agent thread: {e}", exc_info=True)
            result_container["error"] = str(e)
            stream_q.put(None)  # ENSURE STREAM ENDS

    thread = threading.Thread(target=background_task)
    thread.start()

    async def event_generator():
        full_response = ""
        while True:
            # Non-blocking get to allow cooperative yielding in asyncio
            try:
                chunk = stream_q.get(timeout=0.1)
                if chunk is None:
                    break
                full_response += chunk
                # Yield chunk event
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.01)

        thread.join()
        res = result_container.get("result", {})
        err = result_container.get("error")

        # Persist conversation if successful
        if not err and full_response:
            try:
                conv_manager.add_message("user", chat_request.message)
                conv_manager.add_message("assistant", full_response)
            except Exception:
                pass

            try:
                # Use a new DB session since we are spanning threads / generators
                with database.SessionLocal() as local_db:
                    user_msg = models.ChatMessage(
                        conversation_id=db_conversation.id,
                        role="user",
                        content=chat_request.message,
                    )
                    local_db.add(user_msg)

                    sources_json = (
                        json.dumps(res.get("sources")) if res.get("sources") else None
                    )
                    assistant_msg = models.ChatMessage(
                        conversation_id=db_conversation.id,
                        role="assistant",
                        content=full_response,
                        sources_json=sources_json,
                        intent=res.get("intent"),
                    )
                    local_db.add(assistant_msg)
                    local_db.commit()
            except Exception as e:
                logger.error(f"Error persisting streamed chat to DB: {e}")

        # Yield final event with metadata
        final_data = {
            "type": "end",
            "sources": res.get("sources", []),
            "session_id": conv_manager.session_key,
            "conversation_id": db_conversation.id,
            "intent": res.get("intent", "error" if err else "unknown"),
            "latency": res.get("latency", 0),
        }
        if err:
            final_data["error"] = err

        yield f"data: {json.dumps(final_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
