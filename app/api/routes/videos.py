"""Video CRUD endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Video, Transcript

router = APIRouter()


class TranscriptResponse(BaseModel):
    """Transcript response model."""

    id: int
    language_code: str
    is_auto_generated: bool
    clean_content: str
    created_at: datetime

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    """Video response model."""

    id: str
    title: str
    description: Optional[str]
    published_at: Optional[datetime]
    duration_seconds: Optional[int]
    tags: list[str]
    thumbnail_url: Optional[str]
    channel_id: str
    view_count: Optional[int]
    sync_status: str
    sync_error: Optional[str]
    synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    has_transcript: bool = False

    class Config:
        from_attributes = True


class VideoDetailResponse(VideoResponse):
    """Video detail response with transcripts."""

    transcripts: list[TranscriptResponse] = []


class VideoListResponse(BaseModel):
    """Paginated video list response."""

    items: list[VideoResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=VideoListResponse)
def list_videos(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by sync status"),
    search: Optional[str] = Query(None, description="Search in title"),
):
    """List all videos with pagination and filters."""
    query = db.query(Video)

    # Apply filters
    if status:
        query = query.filter(Video.sync_status == status)
    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    videos = query.order_by(Video.published_at.desc()).offset(offset).limit(page_size).all()

    # Check for transcripts
    video_responses = []
    for video in videos:
        response = VideoResponse.model_validate(video)
        response.has_transcript = len(video.transcripts) > 0
        video_responses.append(response)

    return VideoListResponse(
        items=video_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{video_id}", response_model=VideoDetailResponse)
def get_video(video_id: str, db: Session = Depends(get_db)):
    """Get a single video with its transcripts."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    response = VideoDetailResponse.model_validate(video)
    response.has_transcript = len(video.transcripts) > 0
    response.transcripts = [
        TranscriptResponse.model_validate(t) for t in video.transcripts
    ]

    return response


@router.delete("/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    """Delete a video and its transcripts."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    db.delete(video)
    db.commit()

    return {"message": f"Video {video_id} deleted"}
