"""SQLAlchemy ORM models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Video(Base):
    """YouTube video metadata."""

    __tablename__ = "videos"

    id = Column(String(20), primary_key=True)  # YouTube video ID
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    tags = Column(JSON, default=list)  # Stored as JSON array
    thumbnail_url = Column(String(500), nullable=True)
    channel_id = Column(String(50), nullable=False)
    view_count = Column(Integer, nullable=True)

    # Sync tracking
    sync_status = Column(String(20), default="pending")  # pending, synced, error
    sync_error = Column(Text, nullable=True)
    synced_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transcripts = relationship("Transcript", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Video {self.id}: {self.title[:50]}>"


class Transcript(Base):
    """Video transcript/subtitles."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(20), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    language_code = Column(String(10), nullable=False)  # e.g., "en", "fa"
    is_auto_generated = Column(Boolean, default=False)
    raw_content = Column(Text, nullable=False)  # Original with timestamps
    clean_content = Column(Text, nullable=False)  # Plain text, cleaned
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    video = relationship("Video", back_populates="transcripts")

    def __repr__(self) -> str:
        return f"<Transcript {self.id} for video {self.video_id} ({self.language_code})>"
