"""Whisper transcription API routes."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.db.models import Video, Transcript
from app.services.whisper import WhisperService

logger = logging.getLogger(__name__)
router = APIRouter()


class WhisperCandidateResponse(BaseModel):
    """Video candidate for Whisper transcription."""

    id: str
    title: str
    duration_seconds: Optional[int]
    published_at: Optional[datetime]
    estimated_cost: float

    class Config:
        from_attributes = True


class WhisperCandidatesResponse(BaseModel):
    """List of videos that need Whisper transcription."""

    items: list[WhisperCandidateResponse]
    total: int
    total_estimated_cost: float


class TranscribeRequest(BaseModel):
    """Request to transcribe a video."""

    language: str = "fa"  # Default to Persian


class TranscribeResponse(BaseModel):
    """Response from transcription."""

    video_id: str
    success: bool
    message: str
    language_code: Optional[str] = None
    transcript_id: Optional[int] = None
    cost_estimate: Optional[float] = None


class BatchTranscribeRequest(BaseModel):
    """Request to transcribe multiple videos."""

    video_ids: list[str]
    language: str = "fa"


class BatchTranscribeResponse(BaseModel):
    """Response from batch transcription."""

    message: str
    total_videos: int
    total_estimated_cost: float


@router.get("/candidates", response_model=WhisperCandidatesResponse)
def get_whisper_candidates(db: Session = Depends(get_db)):
    """
    Get list of videos without transcripts that could be transcribed with Whisper.
    """
    # Find synced videos without transcripts
    videos_without_transcripts = (
        db.query(Video)
        .filter(Video.sync_status == "synced")
        .outerjoin(Transcript)
        .filter(Transcript.id.is_(None))
        .order_by(Video.published_at.desc())
        .all()
    )

    candidates = []
    total_cost = 0.0

    for video in videos_without_transcripts:
        duration = video.duration_seconds or 0
        cost = (duration / 60) * 0.006  # $0.006 per minute
        total_cost += cost

        candidates.append(
            WhisperCandidateResponse(
                id=video.id,
                title=video.title,
                duration_seconds=video.duration_seconds,
                published_at=video.published_at,
                estimated_cost=round(cost, 3),
            )
        )

    return WhisperCandidatesResponse(
        items=candidates,
        total=len(candidates),
        total_estimated_cost=round(total_cost, 2),
    )


@router.post("/transcribe/{video_id}", response_model=TranscribeResponse)
def transcribe_video(
    video_id: str,
    request: TranscribeRequest,
    db: Session = Depends(get_db),
):
    """
    Transcribe a single video using Whisper.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Add OPENAI_API_KEY to .env",
        )

    # Check video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if Whisper transcript already exists (allow if only YouTube transcript exists)
    existing_whisper = (
        db.query(Transcript)
        .filter(Transcript.video_id == video_id)
        .filter(Transcript.source == "whisper")
        .first()
    )
    if existing_whisper:
        return TranscribeResponse(
            video_id=video_id,
            success=False,
            message="Video already has a Whisper transcript",
        )

    # Estimate cost
    duration = video.duration_seconds or 0
    cost_estimate = (duration / 60) * 0.006

    try:
        # Initialize service and transcribe
        whisper_service = WhisperService(api_key=settings.openai_api_key)
        result = whisper_service.transcribe_video(video_id, language=request.language)

        if not result:
            return TranscribeResponse(
                video_id=video_id,
                success=False,
                message="Transcription failed. Check logs for details.",
                cost_estimate=cost_estimate,
            )

        # Save to database
        transcript = Transcript(
            video_id=video_id,
            language_code=result.language_code,
            is_auto_generated=False,  # Whisper is not "auto-generated" in YouTube sense
            source="whisper",
            raw_content=result.raw_content,
            clean_content=result.clean_content,
        )
        db.add(transcript)
        db.commit()
        db.refresh(transcript)

        return TranscribeResponse(
            video_id=video_id,
            success=True,
            message="Transcription completed successfully",
            language_code=result.language_code,
            transcript_id=transcript.id,
            cost_estimate=cost_estimate,
        )

    except Exception as e:
        logger.error(f"Error transcribing video {video_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription error: {str(e)}",
        )


@router.post("/transcribe/batch", response_model=BatchTranscribeResponse)
def transcribe_batch(
    request: BatchTranscribeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Queue multiple videos for Whisper transcription (runs in background).
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Add OPENAI_API_KEY to .env",
        )

    # Calculate total cost estimate
    total_duration = 0
    valid_videos = []

    for video_id in request.video_ids:
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            # Check no existing Whisper transcript (allow if only YouTube transcript exists)
            existing_whisper = (
                db.query(Transcript)
                .filter(Transcript.video_id == video_id)
                .filter(Transcript.source == "whisper")
                .first()
            )
            if not existing_whisper:
                valid_videos.append(video_id)
                total_duration += video.duration_seconds or 0

    total_cost = (total_duration / 60) * 0.006

    if not valid_videos:
        return BatchTranscribeResponse(
            message="No videos need transcription",
            total_videos=0,
            total_estimated_cost=0,
        )

    # Queue background transcription
    # Note: For production, use a proper task queue like Celery
    background_tasks.add_task(
        _batch_transcribe_task,
        valid_videos,
        request.language,
        settings.openai_api_key,
    )

    return BatchTranscribeResponse(
        message=f"Queued {len(valid_videos)} videos for transcription",
        total_videos=len(valid_videos),
        total_estimated_cost=round(total_cost, 2),
    )


def _batch_transcribe_task(video_ids: list[str], language: str, api_key: str):
    """Background task to transcribe multiple videos."""
    from app.db.database import SessionLocal

    whisper_service = WhisperService(api_key=api_key)
    db = SessionLocal()

    try:
        for video_id in video_ids:
            logger.info(f"Batch transcribing video: {video_id}")
            try:
                result = whisper_service.transcribe_video(video_id, language=language)
                if result:
                    transcript = Transcript(
                        video_id=video_id,
                        language_code=result.language_code,
                        is_auto_generated=False,
                        source="whisper",
                        raw_content=result.raw_content,
                        clean_content=result.clean_content,
                    )
                    db.add(transcript)
                    db.commit()
                    logger.info(f"Transcribed {video_id} successfully")
                else:
                    logger.error(f"Failed to transcribe {video_id}")
            except Exception as e:
                logger.error(f"Error transcribing {video_id}: {e}")
                continue
    finally:
        db.close()


@router.get("/cost-estimate/{video_id}")
def get_cost_estimate(video_id: str, db: Session = Depends(get_db)):
    """Get cost estimate for transcribing a video."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    duration = video.duration_seconds or 0
    cost = (duration / 60) * 0.006

    return {
        "video_id": video_id,
        "duration_seconds": duration,
        "duration_minutes": round(duration / 60, 1),
        "estimated_cost_usd": round(cost, 3),
    }


# ============================================================================
# YouTube Caption Upload Endpoints
# ============================================================================


class UploadCaptionRequest(BaseModel):
    """Request to upload caption to YouTube."""

    language: str = "fa"
    name: str = ""
    is_draft: bool = False


class UploadCaptionResponse(BaseModel):
    """Response from caption upload."""

    video_id: str
    success: bool
    message: str
    caption_id: Optional[str] = None


class YouTubeAuthStatus(BaseModel):
    """YouTube OAuth status."""

    authenticated: bool
    message: str


@router.get("/youtube/auth-status", response_model=YouTubeAuthStatus)
def get_youtube_auth_status():
    """Check if YouTube OAuth is configured and authenticated."""
    from pathlib import Path

    credentials_path = Path("data/client_secrets.json")
    token_path = Path("data/youtube_token.json")

    if not credentials_path.exists():
        return YouTubeAuthStatus(
            authenticated=False,
            message="OAuth credentials not found. Download client_secrets.json from Google Cloud Console.",
        )

    if not token_path.exists():
        return YouTubeAuthStatus(
            authenticated=False,
            message="Not authenticated. Call /whisper/youtube/authenticate to authorize.",
        )

    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()
        if service.is_authenticated():
            return YouTubeAuthStatus(
                authenticated=True,
                message="Authenticated and ready to upload captions.",
            )
        else:
            return YouTubeAuthStatus(
                authenticated=False,
                message="Token expired. Call /whisper/youtube/authenticate to re-authorize.",
            )
    except Exception as e:
        return YouTubeAuthStatus(
            authenticated=False,
            message=f"Authentication error: {str(e)}",
        )


@router.post("/youtube/authenticate")
def authenticate_youtube():
    """
    Initiate YouTube OAuth authentication.
    This will open a browser window for authorization.
    """
    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()
        # This will trigger the OAuth flow
        service._get_credentials()
        return {"success": True, "message": "Successfully authenticated with YouTube"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.post("/youtube/upload/{video_id}", response_model=UploadCaptionResponse)
def upload_caption_to_youtube(
    video_id: str,
    request: UploadCaptionRequest,
    db: Session = Depends(get_db),
):
    """
    Upload a Whisper transcript as a caption to YouTube.
    Requires OAuth authentication first.
    """
    # Check transcript exists
    transcript = (
        db.query(Transcript)
        .filter(Transcript.video_id == video_id)
        .filter(Transcript.source == "whisper")
        .first()
    )

    if not transcript:
        raise HTTPException(
            status_code=404,
            detail="No Whisper transcript found for this video. Transcribe first.",
        )

    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()

        # Upload the raw content (with timestamps) - will be converted to SRT
        result = service.upload_caption(
            video_id=video_id,
            transcript=transcript.raw_content,
            language=request.language,
            name=request.name or f"Whisper ({request.language})",
            is_draft=request.is_draft,
            replace_existing=True,
        )

        return UploadCaptionResponse(
            video_id=video_id,
            success=True,
            message="Caption uploaded successfully",
            caption_id=result.get("id"),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading caption for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/youtube/captions/{video_id}")
def list_youtube_captions(video_id: str):
    """List existing captions for a video on YouTube."""
    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()
        captions = service.list_captions(video_id)
        return {"video_id": video_id, "captions": captions}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing captions for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============================================================================
# Transcript Cleanup Endpoints
# ============================================================================


class CleanupRequest(BaseModel):
    """Request to clean up a transcript."""

    transcript_id: Optional[int] = None  # If provided, use this transcript
    language: str = "fa"
    preserve_timestamps: bool = True
    channel_context: str = "Persian programming and software development tutorials"  # Default context


class CleanupResponse(BaseModel):
    """Response from transcript cleanup."""

    video_id: str
    success: bool
    message: str
    original: Optional[str] = None
    cleaned: Optional[str] = None
    changes_summary: Optional[str] = None
    cost_estimate: Optional[float] = None


@router.post("/cleanup/{video_id}", response_model=CleanupResponse)
def cleanup_transcript(
    video_id: str,
    request: CleanupRequest,
    db: Session = Depends(get_db),
):
    """
    Clean up a transcript using GPT to fix errors and improve formatting.
    Returns both original and cleaned versions for comparison.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Add OPENAI_API_KEY to .env",
        )

    # Get transcript
    if request.transcript_id:
        transcript = (
            db.query(Transcript)
            .filter(Transcript.id == request.transcript_id)
            .first()
        )
    else:
        # Get the best transcript (Whisper first, then YouTube)
        transcript = (
            db.query(Transcript)
            .filter(Transcript.video_id == video_id)
            .order_by(
                # Whisper transcripts first
                (Transcript.source == "whisper").desc()
            )
            .first()
        )

    if not transcript:
        raise HTTPException(
            status_code=404,
            detail="No transcript found for this video",
        )

    # Get video metadata for context
    video = db.query(Video).filter(Video.id == video_id).first()

    try:
        from app.services.transcript_cleanup import TranscriptCleanupService

        service = TranscriptCleanupService(api_key=settings.openai_api_key)

        # Estimate cost first
        cost_estimate = service.estimate_cost(transcript.raw_content)

        # Perform cleanup with video context
        result = service.cleanup_transcript(
            transcript=transcript.raw_content,
            language_code=request.language,
            preserve_timestamps=request.preserve_timestamps,
            video_title=video.title if video else "",
            video_description=video.description if video else "",
            video_tags=video.tags if video else [],
            channel_context=request.channel_context,
        )

        if not result:
            return CleanupResponse(
                video_id=video_id,
                success=False,
                message="Cleanup failed. Check logs for details.",
                cost_estimate=cost_estimate,
            )

        return CleanupResponse(
            video_id=video_id,
            success=True,
            message="Transcript cleaned successfully",
            original=result.original,
            cleaned=result.cleaned,
            changes_summary=result.changes_summary,
            cost_estimate=cost_estimate,
        )

    except Exception as e:
        logger.error(f"Error cleaning transcript for {video_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup error: {str(e)}",
        )


class SaveCleanedRequest(BaseModel):
    """Request to save a cleaned transcript."""

    cleaned_content: str
    language: str = "fa"


@router.post("/cleanup/{video_id}/save")
def save_cleaned_transcript(
    video_id: str,
    request: SaveCleanedRequest,
    db: Session = Depends(get_db),
):
    """
    Save a cleaned transcript as a new transcript entry.
    """
    # Check video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Create new transcript with source "cleaned"
    transcript = Transcript(
        video_id=video_id,
        language_code=request.language,
        is_auto_generated=False,
        source="cleaned",  # Mark as cleaned version
        raw_content=request.cleaned_content,
        clean_content=request.cleaned_content.replace(
            # Remove timestamps for clean content
            r"\[\d{1,2}:\d{2}(:\d{2})?\]\s*", ""
        ),
    )

    db.add(transcript)
    db.commit()
    db.refresh(transcript)

    return {
        "video_id": video_id,
        "transcript_id": transcript.id,
        "success": True,
        "message": "Cleaned transcript saved",
    }


class UploadCleanedRequest(BaseModel):
    """Request to upload cleaned transcript to YouTube."""

    cleaned_content: str
    language: str = "fa"
    is_draft: bool = False


@router.post("/youtube/upload-cleaned/{video_id}")
def upload_cleaned_to_youtube(
    video_id: str,
    request: UploadCleanedRequest,
    db: Session = Depends(get_db),
):
    """
    Upload a cleaned transcript directly to YouTube without saving.
    """
    # Check video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()

        # Upload with timestamps - will be converted to SRT format
        result = service.upload_caption(
            video_id=video_id,
            transcript=request.cleaned_content,
            language=request.language,
            name=f"Cleaned ({request.language})",
            is_draft=request.is_draft,
            replace_existing=True,
        )

        return {
            "video_id": video_id,
            "success": True,
            "message": "Cleaned transcript uploaded to YouTube",
            "caption_id": result.get("id"),
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading cleaned transcript for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
