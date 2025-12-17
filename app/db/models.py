from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, Boolean, Text, ForeignKey, Column, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String, primary_key=True) # SHA256 deterministic ID
    title: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(String, unique=True, index=True)
    content_raw: Mapped[str] = mapped_column(Text)
    content_clean: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String) # 'gov' or 'independent'
    language: Mapped[str] = mapped_column(String) # 'en' or 'te'
    domain: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    pub_date: Mapped[datetime] = mapped_column(DateTime)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Validation flags
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class Narrative(Base):
    __tablename__ = "narratives"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String)
    week_number: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    narrative_text: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String)
    action_items: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TokenUsage(Base):
    __tablename__ = "token_usage"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    optimized_savings: Mapped[int] = mapped_column(Integer) # How many tokens saved by optimizer
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
