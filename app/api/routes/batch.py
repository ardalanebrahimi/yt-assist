"""Batch processing API routes with Server-Sent Events for progress."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.db.models import Video, Transcript

logger = logging.getLogger(__name__)
router = APIRouter()


def sse_message(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/whisper/candidates")
def get_whisper_candidates(
    db: Session = Depends(get_db),
):
    """Get videos that need Whisper transcription (no whisper transcript yet)."""
    # Get all synced videos
    videos = db.query(Video).filter(Video.sync_status == "synced").all()

    candidates = []
    already_done = []

    for video in videos:
        # Check if video has a whisper transcript
        has_whisper = db.query(Transcript).filter(
            Transcript.video_id == video.id,
            Transcript.source == "whisper"
        ).first() is not None

        if has_whisper:
            already_done.append({
                "id": video.id,
                "title": video.title,
                "duration_seconds": video.duration_seconds,
            })
        else:
            candidates.append({
                "id": video.id,
                "title": video.title,
                "duration_seconds": video.duration_seconds,
                "estimated_cost": round((video.duration_seconds or 0) / 60 * 0.006, 3),
            })

    total_cost = sum(c["estimated_cost"] for c in candidates)
    total_duration = sum(c["duration_seconds"] or 0 for c in candidates)

    return {
        "candidates": candidates,
        "already_done": already_done,
        "summary": {
            "total_candidates": len(candidates),
            "already_done": len(already_done),
            "total_duration_minutes": round(total_duration / 60, 1),
            "estimated_total_cost": round(total_cost, 2),
        }
    }


@router.get("/cleanup/candidates")
def get_cleanup_candidates(
    db: Session = Depends(get_db),
):
    """Get videos that need cleanup (have transcript but no cleaned version)."""
    # Get all videos with transcripts
    videos_with_transcripts = (
        db.query(Video)
        .join(Transcript, Video.id == Transcript.video_id)
        .filter(Video.sync_status == "synced")
        .distinct()
        .all()
    )

    candidates = []
    already_done = []

    for video in videos_with_transcripts:
        # Check if video has a cleaned transcript
        has_cleaned = db.query(Transcript).filter(
            Transcript.video_id == video.id,
            Transcript.source == "cleaned"
        ).first() is not None

        # Get best source transcript for cleanup
        source_transcript = (
            db.query(Transcript)
            .filter(Transcript.video_id == video.id)
            .filter(Transcript.source.in_(["whisper", "youtube"]))
            .order_by((Transcript.source == "whisper").desc())
            .first()
        )

        if has_cleaned:
            already_done.append({
                "id": video.id,
                "title": video.title,
            })
        elif source_transcript:
            # Estimate cost based on transcript length
            char_count = len(source_transcript.raw_content)
            estimated_tokens = char_count / 3
            estimated_cost = round((estimated_tokens / 1_000_000) * 0.75, 4)

            candidates.append({
                "id": video.id,
                "title": video.title,
                "source": source_transcript.source,
                "char_count": char_count,
                "estimated_cost": estimated_cost,
            })

    total_cost = sum(c["estimated_cost"] for c in candidates)

    return {
        "candidates": candidates,
        "already_done": already_done,
        "summary": {
            "total_candidates": len(candidates),
            "already_done": len(already_done),
            "estimated_total_cost": round(total_cost, 4),
        }
    }


@router.get("/whisper/run")
async def batch_whisper(
    video_ids: Optional[str] = Query(None, description="Comma-separated video IDs, or empty for all candidates"),
    language: str = Query("fa", description="Language code"),
    db: Session = Depends(get_db),
):
    """Run Whisper transcription on multiple videos with SSE progress updates."""
    settings = get_settings()

    if not settings.openai_api_key:
        async def error_stream():
            yield sse_message("error", {"message": "OpenAI API key not configured"})
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Determine which videos to process
    if video_ids:
        ids = [id.strip() for id in video_ids.split(",")]
        videos = db.query(Video).filter(Video.id.in_(ids)).all()
    else:
        # Get all candidates (no whisper transcript)
        all_videos = db.query(Video).filter(Video.sync_status == "synced").all()
        videos = []
        for v in all_videos:
            has_whisper = db.query(Transcript).filter(
                Transcript.video_id == v.id,
                Transcript.source == "whisper"
            ).first() is not None
            if not has_whisper:
                videos.append(v)

    async def generate():
        from app.services.whisper import WhisperService

        total = len(videos)
        completed = 0
        skipped = 0
        failed = 0

        yield sse_message("start", {
            "total": total,
            "message": f"Starting Whisper transcription for {total} videos"
        })

        try:
            service = WhisperService(api_key=settings.openai_api_key)
        except Exception as e:
            yield sse_message("error", {"message": f"Failed to initialize Whisper: {str(e)}"})
            return

        for i, video in enumerate(videos):
            # Check again if already has whisper (in case of concurrent runs)
            has_whisper = db.query(Transcript).filter(
                Transcript.video_id == video.id,
                Transcript.source == "whisper"
            ).first() is not None

            if has_whisper:
                skipped += 1
                yield sse_message("progress", {
                    "current": i + 1,
                    "total": total,
                    "video_id": video.id,
                    "title": video.title,
                    "status": "skipped",
                    "message": "Already has Whisper transcript",
                    "completed": completed,
                    "skipped": skipped,
                    "failed": failed,
                })
                continue

            yield sse_message("progress", {
                "current": i + 1,
                "total": total,
                "video_id": video.id,
                "title": video.title,
                "status": "processing",
                "message": f"Transcribing ({video.duration_seconds or 0}s)...",
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
            })

            try:
                result = service.transcribe_video(video.id, language=language)

                if result:
                    # Save to database
                    transcript = Transcript(
                        video_id=video.id,
                        language_code=result.language_code,
                        is_auto_generated=False,
                        source="whisper",
                        raw_content=result.raw_content,
                        clean_content=result.clean_content,
                    )
                    db.add(transcript)
                    db.commit()

                    completed += 1
                    yield sse_message("progress", {
                        "current": i + 1,
                        "total": total,
                        "video_id": video.id,
                        "title": video.title,
                        "status": "done",
                        "message": "Transcription complete",
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })
                else:
                    failed += 1
                    yield sse_message("progress", {
                        "current": i + 1,
                        "total": total,
                        "video_id": video.id,
                        "title": video.title,
                        "status": "failed",
                        "message": "Transcription failed",
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

            except Exception as e:
                failed += 1
                logger.error(f"Error transcribing {video.id}: {e}")
                yield sse_message("progress", {
                    "current": i + 1,
                    "total": total,
                    "video_id": video.id,
                    "title": video.title,
                    "status": "failed",
                    "message": str(e)[:100],
                    "completed": completed,
                    "skipped": skipped,
                    "failed": failed,
                })

        yield sse_message("complete", {
            "total": total,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "message": f"Batch complete: {completed} transcribed, {skipped} skipped, {failed} failed"
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/cleanup/run")
async def batch_cleanup(
    video_ids: Optional[str] = Query(None, description="Comma-separated video IDs, or empty for all candidates"),
    language: str = Query("fa", description="Language code"),
    preserve_timestamps: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Run GPT cleanup on multiple videos with SSE progress updates."""
    settings = get_settings()

    if not settings.openai_api_key:
        async def error_stream():
            yield sse_message("error", {"message": "OpenAI API key not configured"})
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Determine which videos to process
    if video_ids:
        ids = [id.strip() for id in video_ids.split(",")]
        # Get videos that have transcripts
        videos_data = []
        for vid in ids:
            video = db.query(Video).filter(Video.id == vid).first()
            if video:
                transcript = (
                    db.query(Transcript)
                    .filter(Transcript.video_id == vid)
                    .filter(Transcript.source.in_(["whisper", "youtube"]))
                    .order_by((Transcript.source == "whisper").desc())
                    .first()
                )
                if transcript:
                    videos_data.append((video, transcript))
    else:
        # Get all candidates (have transcript but no cleaned version)
        all_videos = (
            db.query(Video)
            .join(Transcript, Video.id == Transcript.video_id)
            .filter(Video.sync_status == "synced")
            .distinct()
            .all()
        )
        videos_data = []
        for video in all_videos:
            has_cleaned = db.query(Transcript).filter(
                Transcript.video_id == video.id,
                Transcript.source == "cleaned"
            ).first() is not None

            if not has_cleaned:
                transcript = (
                    db.query(Transcript)
                    .filter(Transcript.video_id == video.id)
                    .filter(Transcript.source.in_(["whisper", "youtube"]))
                    .order_by((Transcript.source == "whisper").desc())
                    .first()
                )
                if transcript:
                    videos_data.append((video, transcript))

    async def generate():
        from app.services.transcript_cleanup import TranscriptCleanupService
        import re

        total = len(videos_data)
        completed = 0
        skipped = 0
        failed = 0

        yield sse_message("start", {
            "total": total,
            "message": f"Starting cleanup for {total} videos"
        })

        try:
            service = TranscriptCleanupService(api_key=settings.openai_api_key)
        except Exception as e:
            yield sse_message("error", {"message": f"Failed to initialize cleanup service: {str(e)}"})
            return

        for i, (video, source_transcript) in enumerate(videos_data):
            # Check again if already has cleaned (in case of concurrent runs)
            has_cleaned = db.query(Transcript).filter(
                Transcript.video_id == video.id,
                Transcript.source == "cleaned"
            ).first() is not None

            if has_cleaned:
                skipped += 1
                yield sse_message("progress", {
                    "current": i + 1,
                    "total": total,
                    "video_id": video.id,
                    "title": video.title,
                    "status": "skipped",
                    "message": "Already has cleaned transcript",
                    "completed": completed,
                    "skipped": skipped,
                    "failed": failed,
                })
                continue

            yield sse_message("progress", {
                "current": i + 1,
                "total": total,
                "video_id": video.id,
                "title": video.title,
                "status": "processing",
                "message": f"Cleaning transcript ({len(source_transcript.raw_content)} chars)...",
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
            })

            try:
                result = service.cleanup_transcript(
                    transcript=source_transcript.raw_content,
                    language_code=language,
                    preserve_timestamps=preserve_timestamps,
                    video_title=video.title,
                    video_description=video.description or "",
                    video_tags=video.tags or [],
                    channel_context="Persian programming and software development tutorials",
                )

                if result:
                    # Save to database
                    transcript = Transcript(
                        video_id=video.id,
                        language_code=language,
                        is_auto_generated=False,
                        source="cleaned",
                        raw_content=result.cleaned,
                        clean_content=re.sub(
                            r"\[\d{1,2}:\d{2}(:\d{2})?\]\s*",
                            "",
                            result.cleaned,
                        ),
                    )
                    db.add(transcript)
                    db.commit()

                    completed += 1
                    yield sse_message("progress", {
                        "current": i + 1,
                        "total": total,
                        "video_id": video.id,
                        "title": video.title,
                        "status": "done",
                        "message": f"Cleanup complete ({result.changes_summary})",
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })
                else:
                    failed += 1
                    yield sse_message("progress", {
                        "current": i + 1,
                        "total": total,
                        "video_id": video.id,
                        "title": video.title,
                        "status": "failed",
                        "message": "Cleanup failed",
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

            except Exception as e:
                failed += 1
                logger.error(f"Error cleaning {video.id}: {e}")
                yield sse_message("progress", {
                    "current": i + 1,
                    "total": total,
                    "video_id": video.id,
                    "title": video.title,
                    "status": "failed",
                    "message": str(e)[:100],
                    "completed": completed,
                    "skipped": skipped,
                    "failed": failed,
                })

        yield sse_message("complete", {
            "total": total,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "message": f"Batch complete: {completed} cleaned, {skipped} skipped, {failed} failed"
        })

    return StreamingResponse(generate(), media_type="text/event-stream")
