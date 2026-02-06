from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    groups = relationship("UserGroup", back_populates="user")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    prompt_type = Column(String, default="technical")  # technical, compliance, general
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    users = relationship("UserGroup", back_populates="group")
    documents = relationship("Document", back_populates="group")


class UserGroup(Base):
    __tablename__ = "user_groups"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), primary_key=True)
    role = Column(String, default="member")  # member, manager

    user = relationship("User", back_populates="groups")
    group = relationship("Group", back_populates="users")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    file_hash = Column(String, index=True, nullable=True)  # SHA256 hash for dedup
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    group_id = Column(Integer, ForeignKey("groups.id"))

    # Metadata stored as JSON string or separate table if complex
    metadata_json = Column(String, nullable=True)

    group = relationship("Group", back_populates="documents")


class Conversation(Base):
    """Stores chat conversation sessions for persistence like ChatGPT."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    title = Column(String, default="New Chat")
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", backref="conversations")
    group = relationship("Group")
    messages = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """Stores individual chat messages within a conversation."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role = Column(String)  # 'user' or 'assistant'
    content = Column(String)
    sources_json = Column(String, nullable=True)  # JSON string of sources
    intent = Column(String, nullable=True)  # Intent classification for the message
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    conversation = relationship("Conversation", back_populates="messages")
