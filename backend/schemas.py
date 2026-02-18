from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# Token
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# User
class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Group
class GroupBase(BaseModel):
    name: str
    prompt_type: Optional[str] = "technical"  # technical, compliance, general


class GroupCreate(GroupBase):
    pass


class Group(GroupBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# UserGroup
class UserGroupUnnassigned(BaseModel):
    user_id: int
    group_id: int
    role: str  # member, manager

    class Config:
        from_attributes = True


# Query
class QueryRequest(BaseModel):
    query: str
    group_id: Optional[int] = None


# Document
class Document(BaseModel):
    id: int
    filename: str
    file_path: str
    group_id: int
    upload_date: datetime

    class Config:
        from_attributes = True


# Chat
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None  # Link to persistent conversation
    group_id: Optional[int] = None
    filters: Optional[dict] = None  # Optional metadata filters
    model_provider: Optional[str] = None  # "ollama" or "nvidia"
    model_name: Optional[str] = (
        None  # e.g. "gemma3:4b" or "meta/llama-3.3-70b-instruct"
    )


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str
    conversation_id: Optional[int] = None  # Persistent conversation ID
    intent: Optional[str] = None  # greeting, document_query, follow_up, etc.
    latency: Optional[dict] = None


# Conversation (persistent chat history)
class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[List[dict]] = None
    intent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"
    group_id: Optional[int] = None


class ConversationUpdate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: int
    title: str
    group_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0
    last_message: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationResponse):
    messages: List[ChatMessageResponse] = []
