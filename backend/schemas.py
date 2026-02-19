import re
import html
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime


def _sanitize(value: str, max_length: int, field_name: str) -> str:
    """Strip HTML tags, limit length, and whitespace-normalize a string."""
    if not value:
        return value
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", "", value)
    # Unescape any HTML entities
    cleaned = html.unescape(cleaned)
    # Trim to max length
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return cleaned.strip()


# Token
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# User
class UserBase(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            raise ValueError("Invalid email format")
        if len(v) > 255:
            raise ValueError("Email must be at most 255 characters")
        return v


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v


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

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return _sanitize(v, 100, "Group name")

    @field_validator("prompt_type")
    @classmethod
    def validate_prompt_type(cls, v):
        allowed = {"technical", "compliance", "general"}
        if v and v not in allowed:
            raise ValueError(f"prompt_type must be one of: {', '.join(allowed)}")
        return v


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

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        allowed = {"member", "manager"}
        if v not in allowed:
            raise ValueError(f"role must be one of: {', '.join(allowed)}")
        return v

    class Config:
        from_attributes = True


# Query
class QueryRequest(BaseModel):
    query: str
    group_id: Optional[int] = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        return _sanitize(v, 2000, "Query")


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
    conversation_id: Optional[int] = None
    group_id: Optional[int] = None
    filters: Optional[dict] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        return _sanitize(v, 2000, "Message")

    @field_validator("model_provider")
    @classmethod
    def validate_provider(cls, v):
        if v is not None and v not in {"ollama", "nvidia"}:
            raise ValueError("model_provider must be 'ollama' or 'nvidia'")
        return v


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str
    conversation_id: Optional[int] = None
    intent: Optional[str] = None
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

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if v:
            return _sanitize(v, 200, "Title")
        return v


class ConversationUpdate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        return _sanitize(v, 200, "Title")


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
