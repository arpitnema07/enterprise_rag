"""
Conversations Router - Endpoints for managing persistent chat history.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from .. import models, schemas, auth, database

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[schemas.ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    List all conversations for the current user, newest first.
    Includes message count and last message preview.
    """
    conversations = (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user.id)
        .order_by(desc(models.Conversation.updated_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []
    for conv in conversations:
        # Get message count and last message
        messages = conv.messages
        message_count = len(messages)
        last_message = None
        if messages:
            last_msg = messages[-1]
            # Truncate long messages
            last_message = (
                last_msg.content[:100] + "..."
                if len(last_msg.content) > 100
                else last_msg.content
            )

        result.append(
            schemas.ConversationResponse(
                id=conv.id,
                title=conv.title,
                group_id=conv.group_id,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=message_count,
                last_message=last_message,
            )
        )

    return result


@router.get("/{conversation_id}", response_model=schemas.ConversationWithMessages)
async def get_conversation(
    conversation_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Get a single conversation with all its messages.
    """
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Build message responses with parsed sources
    messages = []
    for msg in conversation.messages:
        sources = None
        if msg.sources_json:
            try:
                sources = json.loads(msg.sources_json)
            except json.JSONDecodeError:
                sources = None

        messages.append(
            schemas.ChatMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                sources=sources,
                intent=msg.intent,
                created_at=msg.created_at,
            )
        )

    return schemas.ConversationWithMessages(
        id=conversation.id,
        title=conversation.title,
        group_id=conversation.group_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(messages),
        last_message=messages[-1].content[:100] if messages else None,
        messages=messages,
    )


@router.post("", response_model=schemas.ConversationResponse)
async def create_conversation(
    request: schemas.ConversationCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create a new empty conversation.
    """
    # Verify group access if provided
    if request.group_id:
        user_group = (
            db.query(models.UserGroup)
            .filter(
                models.UserGroup.user_id == current_user.id,
                models.UserGroup.group_id == request.group_id,
            )
            .first()
        )
        if not user_group:
            raise HTTPException(status_code=403, detail="No access to this group")

    conversation = models.Conversation(
        user_id=current_user.id,
        title=request.title or "New Chat",
        group_id=request.group_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return schemas.ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        group_id=conversation.group_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
        last_message=None,
    )


@router.put("/{conversation_id}", response_model=schemas.ConversationResponse)
async def update_conversation(
    conversation_id: int,
    request: schemas.ConversationUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Update conversation title.
    """
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = request.title
    db.commit()
    db.refresh(conversation)

    message_count = len(conversation.messages)
    last_message = None
    if conversation.messages:
        last_msg = conversation.messages[-1]
        last_message = (
            last_msg.content[:100] + "..."
            if len(last_msg.content) > 100
            else last_msg.content
        )

    return schemas.ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        group_id=conversation.group_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count,
        last_message=last_message,
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Delete a conversation and all its messages.
    """
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted", "id": conversation_id}
