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
    group_id: Optional[int] = None
    filters: Optional[dict] = None  # Optional metadata filters


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str
