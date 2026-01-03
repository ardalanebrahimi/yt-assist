"""Dubbing API routes - translate and generate TTS audio."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.db.models import Video, Transcript

logger = logging.getLogger(__name__)
router = APIRouter()


class DubbingRequest(BaseModel):
    """Request to create a dubbed audio."""

    transcript_id: Optional[int] = None  # If provided, use this transcript
    source_language: str = "fa"
    target_language: str = "en"
    voice: str = "nova"  # alloy, echo, fable, onyx, nova, shimmer
    model: str = "tts-1"  # tts-1 or tts-1-hd


class DubbingResponse(BaseModel):
    """Response from dubbing operation."""

    video_id: str
    success: bool
    message: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    segments_count: Optional[int] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None


class CostEstimateResponse(BaseModel):
    """Cost estimate for dubbing."""

    video_id: str
    segments: int
    source_characters: int
    estimated_translated_characters: int
    translation_cost_usd: float
    tts_cost_usd: float
    total_cost_usd: float


@router.get("/voices")
def list_voices():
    """List available TTS voices."""
    return {
        "voices": [
            {"id": "alloy", "description": "Neutral, balanced voice"},
            {"id": "echo", "description": "Warm, conversational male voice"},
            {"id": "fable", "description": "Expressive, narrative voice"},
            {"id": "onyx", "description": "Deep, authoritative male voice"},
            {"id": "nova", "description": "Friendly, natural female voice"},
            {"id": "shimmer", "description": "Clear, professional female voice"},
        ],
        "models": [
            {"id": "tts-1", "description": "Standard quality, faster"},
            {"id": "tts-1-hd", "description": "High quality, slower"},
        ],
        "supported_target_languages": [
            {"code": "en", "name": "English"},
            {"code": "de", "name": "German"},
            {"code": "fr", "name": "French"},
            {"code": "es", "name": "Spanish"},
            {"code": "ar", "name": "Arabic"},
            {"code": "tr", "name": "Turkish"},
        ],
    }


@router.get("/{video_id}/cost-estimate", response_model=CostEstimateResponse)
def estimate_dubbing_cost(
    video_id: str,
    target_language: str = "en",
    transcript_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Estimate the cost of dubbing a video."""
    settings = get_settings()

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured",
        )

    # Get transcript
    if transcript_id:
        transcript = (
            db.query(Transcript)
            .filter(Transcript.id == transcript_id)
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

    try:
        from app.services.dubbing import DubbingService

        service = DubbingService(api_key=settings.openai_api_key)
        estimate = service.estimate_cost(transcript.raw_content, target_language)

        return CostEstimateResponse(
            video_id=video_id,
            **estimate,
        )

    except Exception as e:
        logger.error(f"Error estimating cost for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{video_id}/create", response_model=DubbingResponse)
def create_dub(
    video_id: str,
    request: DubbingRequest,
    db: Session = Depends(get_db),
):
    """Create a dubbed audio file from a video's transcript."""
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

    # Get video for context
    video = db.query(Video).filter(Video.id == video_id).first()
    video_context = ""
    if video:
        video_context = f"Title: {video.title}"
        if video.description:
            video_context += f"\nDescription: {video.description[:300]}"

    try:
        from app.services.dubbing import DubbingService

        service = DubbingService(api_key=settings.openai_api_key)

        result = service.dub_transcript(
            transcript=transcript.raw_content,
            source_language=request.source_language,
            target_language=request.target_language,
            voice=request.voice,
            model=request.model,
            video_id=video_id,
            video_context=video_context,
        )

        if not result:
            return DubbingResponse(
                video_id=video_id,
                success=False,
                message="Dubbing failed. Check logs for details.",
            )

        # Generate download URL
        audio_filename = result.audio_path.split("/")[-1].split("\\")[-1]
        audio_url = f"/api/dubbing/audio/{audio_filename}"

        return DubbingResponse(
            video_id=video_id,
            success=True,
            message=f"Dubbed audio created successfully ({result.segments_count} segments)",
            audio_url=audio_url,
            duration_seconds=result.duration_seconds,
            segments_count=result.segments_count,
            source_language=result.source_language,
            target_language=result.target_language,
        )

    except Exception as e:
        logger.error(f"Error creating dub for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{filename}")
def get_audio_file(filename: str):
    """Download a dubbed audio file."""
    from pathlib import Path

    audio_path = Path("data/dubs") / filename

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=filename,
    )


@router.get("/{video_id}/list")
def list_dubs(video_id: str):
    """List available dubbed audio files for a video."""
    from pathlib import Path

    dubs_dir = Path("data/dubs")
    if not dubs_dir.exists():
        return {"video_id": video_id, "dubs": []}

    dubs = []
    for audio_file in dubs_dir.glob(f"{video_id}_*.mp3"):
        # Parse language from filename
        parts = audio_file.stem.split("_")
        language = parts[-1] if len(parts) > 1 else "unknown"

        dubs.append({
            "filename": audio_file.name,
            "language": language,
            "url": f"/api/dubbing/audio/{audio_file.name}",
            "size_bytes": audio_file.stat().st_size,
        })

    return {"video_id": video_id, "dubs": dubs}
