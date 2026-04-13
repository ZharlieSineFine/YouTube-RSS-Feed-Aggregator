"""SQLAlchemy models: sources and stored article/video rows."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    """Logical content source (e.g. one YouTube channel, or Anthropic RSS bundle)."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("kind", "external_ref", name="uq_source_kind_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # youtube | anthropic | openai
    external_ref: Mapped[str] = mapped_column(String(256), default="")  # channel_id or "default"
    label: Mapped[str] = mapped_column(String(512), default="")

    articles: Mapped[List["Article"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Article(Base):
    """One ingested URL with optional full text (transcript or markdown)."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(1024))
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summarized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source: Mapped["Source"] = relationship(back_populates="articles")
