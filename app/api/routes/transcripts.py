"""Transcript management API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.db.models import Video, Transcript

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Cleanup Endpoints
# ============================================================================


class CleanupRequest(BaseModel):
    """Request to clean up a transcript."""

    transcript_id: Optional[int] = None  # If provided, use this transcript
    language: str = "fa"
    preserve_timestamps: bool = True
    channel_context: str = "Persian programming and software development tutorials"


class CleanupResponse(BaseModel):
    """Response from transcript cleanup."""

    video_id: str
    success: bool
    message: str
    original: Optional[str] = None
    cleaned: Optional[str] = None
    changes_summary: Optional[str] = None
    cost_estimate: Optional[float] = None


@router.post("/{video_id}/cleanup", response_model=CleanupResponse)
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
        # Get the best transcript (Cleaned first, then Whisper, then YouTube)
        transcript = (
            db.query(Transcript)
            .filter(Transcript.video_id == video_id)
            .order_by(
                (Transcript.source == "cleaned").desc(),
                (Transcript.source == "whisper").desc(),
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


@router.post("/{video_id}/save")
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

    import re
    # Create new transcript with source "cleaned"
    transcript = Transcript(
        video_id=video_id,
        language_code=request.language,
        is_auto_generated=False,
        source="cleaned",
        raw_content=request.cleaned_content,
        clean_content=re.sub(
            r"\[\d{1,2}:\d{2}(:\d{2})?\]\s*",
            "",
            request.cleaned_content,
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


# ============================================================================
# YouTube Upload Endpoints
# ============================================================================


class YouTubeUploadRequest(BaseModel):
    """Request to upload transcript to YouTube."""

    language: str = "fa"
    name: str = ""
    is_draft: bool = False


class YouTubeUploadResponse(BaseModel):
    """Response from YouTube upload."""

    video_id: str
    success: bool
    message: str
    caption_id: Optional[str] = None


@router.post("/{video_id}/youtube/upload", response_model=YouTubeUploadResponse)
def upload_to_youtube(
    video_id: str,
    request: YouTubeUploadRequest,
    db: Session = Depends(get_db),
):
    """
    Upload the best available transcript to YouTube.
    Prioritizes: Cleaned > Whisper > YouTube source.
    """
    # Get the best transcript
    transcript = (
        db.query(Transcript)
        .filter(Transcript.video_id == video_id)
        .order_by(
            (Transcript.source == "cleaned").desc(),
            (Transcript.source == "whisper").desc(),
        )
        .first()
    )

    if not transcript:
        raise HTTPException(
            status_code=404,
            detail="No transcript found for this video",
        )

    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()

        result = service.upload_caption(
            video_id=video_id,
            transcript=transcript.raw_content,
            language=request.language,
            name=request.name or f"{transcript.source.title()} ({request.language})",
            is_draft=request.is_draft,
            replace_existing=True,
        )

        return YouTubeUploadResponse(
            video_id=video_id,
            success=True,
            message=f"Transcript ({transcript.source}) uploaded to YouTube",
            caption_id=result.get("id"),
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading transcript for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


class YouTubeUploadCleanedRequest(BaseModel):
    """Request to upload specific cleaned content to YouTube."""

    cleaned_content: str
    language: str = "fa"
    is_draft: bool = False


@router.post("/{video_id}/youtube/upload-content")
def upload_content_to_youtube(
    video_id: str,
    request: YouTubeUploadCleanedRequest,
    db: Session = Depends(get_db),
):
    """
    Upload specific transcript content to YouTube (e.g., from diff view).
    """
    # Check video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()

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
            "message": "Transcript uploaded to YouTube",
            "caption_id": result.get("id"),
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading transcript for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ============================================================================
# YouTube Auth Endpoints
# ============================================================================


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
            message="Not authenticated. Click 'Authenticate YouTube' to authorize.",
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
                message="Token expired. Click 'Authenticate YouTube' to re-authorize.",
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
        service._get_credentials()
        return {"success": True, "message": "Successfully authenticated with YouTube"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.get("/{video_id}/youtube/captions")
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


@router.delete("/{video_id}/youtube/captions/{caption_id}")
def delete_youtube_caption(video_id: str, caption_id: str):
    """Delete a caption from YouTube."""
    try:
        from app.services.youtube_captions import YouTubeCaptionService

        service = YouTubeCaptionService()
        success = service.delete_caption(caption_id)
        return {"video_id": video_id, "caption_id": caption_id, "success": success}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting caption {caption_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
