from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    payload = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(10), nullable=False)


class LoginSession(Base):
    __tablename__ = "sessions"

    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    expires_at = Column(String(64))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    key = Column(String(64), primary_key=True)
    count = Column(Integer, nullable=False)
    window_start = Column(Float, nullable=False)
    blocked_until = Column(Float, nullable=True)
