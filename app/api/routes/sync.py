"""Sync operation endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.services.sync import SyncService, SyncStatus

router = APIRouter()


class SyncStatusResponse(BaseModel):
    """Sync status response model."""

    total_videos: int
    synced: int
    pending: int
    errors: int


class SyncResultResponse(BaseModel):
    """Single video sync result."""

    video_id: str
    success: bool
    error: Optional[str] = None
    has_transcript: bool = False


class SyncAllResponse(BaseModel):
    """Response for sync all operation."""

    message: str
    results: list[SyncResultResponse]
    summary: SyncStatusResponse


class SyncRequest(BaseModel):
    """Request body for sync operations."""

    channel_id: Optional[str] = None


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status(db: Session = Depends(get_db)):
    """Get current sync status summary."""
    sync_service = SyncService(db)
    status = sync_service.get_sync_status()

    return SyncStatusResponse(
        total_videos=status.total_videos,
        synced=status.synced,
        pending=status.pending,
        errors=status.errors,
    )


@router.post("/all", response_model=SyncAllResponse)
def sync_all_videos(
    request: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
):
    """
    Sync all videos from the configured YouTube channel.

    This fetches all video metadata and transcripts.
    """
    settings = get_settings()
    channel_id = request.channel_id or settings.channel_id

    sync_service = SyncService(db)
    results = sync_service.sync_all_videos(channel_id)

    # Get updated status
    status = sync_service.get_sync_status()

    return SyncAllResponse(
        message=f"Synced {len(results)} videos from channel {channel_id}",
        results=[
            SyncResultResponse(
                video_id=r.video_id,
                success=r.success,
                error=r.error,
                has_transcript=r.has_transcript,
            )
            for r in results
        ],
        summary=SyncStatusResponse(
            total_videos=status.total_videos,
            synced=status.synced,
            pending=status.pending,
            errors=status.errors,
        ),
    )


@router.post("/video/{video_id}", response_model=SyncResultResponse)
def sync_single_video(video_id: str, db: Session = Depends(get_db)):
    """Sync a single video by its YouTube ID."""
    sync_service = SyncService(db)
    result = sync_service.sync_single_video(video_id)

    return SyncResultResponse(
        video_id=result.video_id,
        success=result.success,
        error=result.error,
        has_transcript=result.has_transcript,
    )
