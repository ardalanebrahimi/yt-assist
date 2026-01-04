"""Batch processing API routes with Server-Sent Events for progress."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.db.models import Video, Transcript
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()

# Default parallel workers for batch operations
DEFAULT_PARALLEL_WORKERS = 2


def _check_youtube_caption_exists(video_id: str, language: str = "fa") -> bool:
    """Check if a video has a caption uploaded to YouTube for the given language."""
    try:
        from app.services.youtube_captions import YouTubeCaptionService
        service = YouTubeCaptionService()
        if not service.is_authenticated():
            return False
        captions = service.list_captions(video_id)
        # Check if there's a non-auto-generated caption for this language
        for cap in captions:
            if cap.get("language") == language and cap.get("track_kind") != "ASR":
                return True
        return False
    except Exception as e:
        logger.warning(f"Failed to check YouTube captions for {video_id}: {e}")
        return False


@router.get("/status/summary")
def get_video_status_summary(
    check_youtube_uploads: bool = Query(False, description="Check YouTube for uploaded captions (slower)"),
    db: Session = Depends(get_db),
):
    """Get summary of all video states (transcripts, cleanup status, etc.)."""
    # Get all synced videos
    videos = db.query(Video).filter(Video.sync_status == "synced").all()

    summary = {
        "total_videos": len(videos),
        "with_youtube_subtitle": 0,
        "with_whisper": 0,
        "with_cleaned": 0,
        "no_transcript": 0,
        "needs_whisper": 0,
        "needs_cleanup": 0,
        "needs_upload": 0,
        "uploaded_to_youtube": 0,
        "fully_processed": 0,
    }

    video_details = []

    for video in videos:
        transcripts = db.query(Transcript).filter(Transcript.video_id == video.id).all()

        has_youtube = any(t.source == "youtube" for t in transcripts)
        has_whisper = any(t.source == "whisper" for t in transcripts)
        has_cleaned = any(t.source == "cleaned" for t in transcripts)
        has_any = len(transcripts) > 0

        # Check if uploaded to YouTube (only if requested, as it's slow)
        uploaded_to_yt = False
        if check_youtube_uploads and (has_whisper or has_cleaned):
            uploaded_to_yt = _check_youtube_caption_exists(video.id)

        if has_youtube:
            summary["with_youtube_subtitle"] += 1
        if has_whisper:
            summary["with_whisper"] += 1
        if has_cleaned:
            summary["with_cleaned"] += 1
        if not has_any:
            summary["no_transcript"] += 1
        if not has_whisper:
            summary["needs_whisper"] += 1
        if has_any and not has_cleaned:
            summary["needs_cleanup"] += 1
        if (has_whisper or has_cleaned) and not uploaded_to_yt and check_youtube_uploads:
            summary["needs_upload"] += 1
        if uploaded_to_yt:
            summary["uploaded_to_youtube"] += 1
        if has_whisper and has_cleaned:
            summary["fully_processed"] += 1

        video_details.append({
            "id": video.id,
            "title": video.title,
            "duration_seconds": video.duration_seconds,
            "has_youtube": has_youtube,
            "has_whisper": has_whisper,
            "has_cleaned": has_cleaned,
            "uploaded_to_yt": uploaded_to_yt if check_youtube_uploads else None,
        })

    return {
        "summary": summary,
        "videos": video_details,
    }


@router.get("/no-transcript/candidates")
def get_no_transcript_candidates(
    db: Session = Depends(get_db),
):
    """Get videos that have no transcript at all (neither YouTube nor Whisper)."""
    # Get all synced videos
    videos = db.query(Video).filter(Video.sync_status == "synced").all()

    candidates = []
    has_transcript = []

    for video in videos:
        # Check if video has any transcript (youtube or whisper)
        has_any = db.query(Transcript).filter(
            Transcript.video_id == video.id,
            Transcript.source.in_(["youtube", "whisper"])
        ).first() is not None

        if has_any:
            has_transcript.append({
                "id": video.id,
                "title": video.title,
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
        "already_done": has_transcript,
        "summary": {
            "total_candidates": len(candidates),
            "already_done": len(has_transcript),
            "total_duration_minutes": round(total_duration / 60, 1),
            "estimated_total_cost": round(total_cost, 2),
        }
    }


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


def _process_whisper_video(
    video_id: str,
    video_title: str,
    video_duration: int,
    language: str,
    auto_upload: bool,
    openai_api_key: str,
) -> dict:
    """
    Process a single video with Whisper transcription.
    This function runs in a thread pool for parallel execution.

    Returns a dict with status and message for SSE updates.
    """
    from app.services.whisper import WhisperService
    from app.services.youtube_captions import YouTubeCaptionService

    # Create a new database session for this thread
    db = SessionLocal()

    try:
        # Check if already has whisper transcript
        has_whisper = db.query(Transcript).filter(
            Transcript.video_id == video_id,
            Transcript.source == "whisper"
        ).first() is not None

        if has_whisper:
            return {
                "video_id": video_id,
                "title": video_title,
                "status": "skipped",
                "message": "Already has Whisper transcript",
            }

        # Initialize services
        whisper_service = WhisperService(api_key=openai_api_key)

        # Transcribe
        result = whisper_service.transcribe_video(video_id, language=language)

        if not result:
            return {
                "video_id": video_id,
                "title": video_title,
                "status": "failed",
                "message": "Transcription failed",
            }

        # Save to database
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

        # Auto-upload to YouTube if enabled
        upload_status = ""
        if auto_upload:
            try:
                caption_service = YouTubeCaptionService()
                if caption_service.is_authenticated():
                    caption_service.upload_caption(
                        video_id=video_id,
                        transcript=result.raw_content,
                        language=language,
                        name=f"Whisper ({language})",
                        replace_existing=False,  # Don't try to delete (saves quota)
                        skip_check=True,  # Skip list_captions call (saves 50 units)
                    )
                    upload_status = " + uploaded to YouTube"
            except Exception as upload_err:
                logger.error(f"Failed to upload caption for {video_id}: {upload_err}")
                upload_status = " (upload failed)"

        return {
            "video_id": video_id,
            "title": video_title,
            "status": "done",
            "message": f"Transcription complete{upload_status}",
        }

    except Exception as e:
        logger.error(f"Error transcribing {video_id}: {e}")
        return {
            "video_id": video_id,
            "title": video_title,
            "status": "failed",
            "message": str(e)[:100],
        }
    finally:
        db.close()


@router.get("/whisper/run")
async def batch_whisper(
    video_ids: Optional[str] = Query(None, description="Comma-separated video IDs, or empty for all candidates"),
    language: str = Query("fa", description="Language code"),
    auto_upload: bool = Query(True, description="Automatically upload to YouTube after transcription"),
    parallel: int = Query(DEFAULT_PARALLEL_WORKERS, description="Number of parallel workers (1-4)", ge=1, le=4),
    db: Session = Depends(get_db),
):
    """Run Whisper transcription on multiple videos with SSE progress updates and parallel processing."""
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

    # Prepare video data for parallel processing
    video_data = [
        {
            "video_id": v.id,
            "video_title": v.title,
            "video_duration": v.duration_seconds or 0,
        }
        for v in videos
    ]

    async def generate():
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(video_data)
        completed = 0
        skipped = 0
        failed = 0
        processed = 0

        yield sse_message("start", {
            "total": total,
            "parallel": parallel,
            "message": f"Starting Whisper transcription for {total} videos with {parallel} parallel workers" +
                       (" (with auto-upload)" if auto_upload else "")
        })

        if total == 0:
            yield sse_message("complete", {
                "total": 0,
                "completed": 0,
                "skipped": 0,
                "failed": 0,
                "message": "No videos to process"
            })
            return

        # Send initial processing status for first N videos
        processing_videos = video_data[:parallel]
        for vd in processing_videos:
            yield sse_message("progress", {
                "current": processed + 1,
                "total": total,
                "video_id": vd["video_id"],
                "title": vd["video_title"],
                "status": "processing",
                "message": f"Transcribing ({vd['video_duration']}s)...",
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
            })

        # Process videos in parallel using ThreadPoolExecutor
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all tasks
            future_to_video = {
                executor.submit(
                    _process_whisper_video,
                    vd["video_id"],
                    vd["video_title"],
                    vd["video_duration"],
                    language,
                    auto_upload,
                    settings.openai_api_key,
                ): vd
                for vd in video_data
            }

            # Process results as they complete
            for future in as_completed(future_to_video):
                vd = future_to_video[future]
                processed += 1

                try:
                    result = future.result()
                    status = result.get("status", "failed")

                    if status == "done":
                        completed += 1
                    elif status == "skipped":
                        skipped += 1
                    else:
                        failed += 1

                    yield sse_message("progress", {
                        "current": processed,
                        "total": total,
                        "video_id": result.get("video_id", vd["video_id"]),
                        "title": result.get("title", vd["video_title"]),
                        "status": status,
                        "message": result.get("message", ""),
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing {vd['video_id']}: {e}")
                    yield sse_message("progress", {
                        "current": processed,
                        "total": total,
                        "video_id": vd["video_id"],
                        "title": vd["video_title"],
                        "status": "failed",
                        "message": str(e)[:100],
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

                # Small delay to allow SSE to flush
                await asyncio.sleep(0.01)

        yield sse_message("complete", {
            "total": total,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "message": f"Batch complete: {completed} transcribed, {skipped} skipped, {failed} failed"
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


def _process_cleanup_video(
    video_id: str,
    video_title: str,
    video_description: str,
    video_tags: list,
    transcript_content: str,
    language: str,
    preserve_timestamps: bool,
    openai_api_key: str,
) -> dict:
    """
    Process a single video with GPT cleanup.
    This function runs in a thread pool for parallel execution.

    Returns a dict with status and message for SSE updates.
    """
    import re
    from app.services.transcript_cleanup import TranscriptCleanupService

    # Create a new database session for this thread
    db = SessionLocal()

    try:
        # Check if already has cleaned transcript
        has_cleaned = db.query(Transcript).filter(
            Transcript.video_id == video_id,
            Transcript.source == "cleaned"
        ).first() is not None

        if has_cleaned:
            return {
                "video_id": video_id,
                "title": video_title,
                "status": "skipped",
                "message": "Already has cleaned transcript",
            }

        # Initialize service
        service = TranscriptCleanupService(api_key=openai_api_key)

        # Clean transcript
        result = service.cleanup_transcript(
            transcript=transcript_content,
            language_code=language,
            preserve_timestamps=preserve_timestamps,
            video_title=video_title,
            video_description=video_description,
            video_tags=video_tags,
            channel_context="Persian programming and software development tutorials",
        )

        if not result:
            return {
                "video_id": video_id,
                "title": video_title,
                "status": "failed",
                "message": "Cleanup failed",
            }

        # Save to database
        transcript = Transcript(
            video_id=video_id,
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

        return {
            "video_id": video_id,
            "title": video_title,
            "status": "done",
            "message": f"Cleanup complete ({result.changes_summary})",
        }

    except Exception as e:
        logger.error(f"Error cleaning {video_id}: {e}")
        return {
            "video_id": video_id,
            "title": video_title,
            "status": "failed",
            "message": str(e)[:100],
        }
    finally:
        db.close()


@router.get("/cleanup/run")
async def batch_cleanup(
    video_ids: Optional[str] = Query(None, description="Comma-separated video IDs, or empty for all candidates"),
    language: str = Query("fa", description="Language code"),
    preserve_timestamps: bool = Query(True),
    parallel: int = Query(DEFAULT_PARALLEL_WORKERS, description="Number of parallel workers (1-4)", ge=1, le=4),
    db: Session = Depends(get_db),
):
    """Run GPT cleanup on multiple videos with SSE progress updates and parallel processing."""
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
                    videos_data.append({
                        "video_id": video.id,
                        "video_title": video.title,
                        "video_description": video.description or "",
                        "video_tags": video.tags or [],
                        "transcript_content": transcript.raw_content,
                        "char_count": len(transcript.raw_content),
                    })
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
                    videos_data.append({
                        "video_id": video.id,
                        "video_title": video.title,
                        "video_description": video.description or "",
                        "video_tags": video.tags or [],
                        "transcript_content": transcript.raw_content,
                        "char_count": len(transcript.raw_content),
                    })

    async def generate():
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(videos_data)
        completed = 0
        skipped = 0
        failed = 0
        processed = 0

        yield sse_message("start", {
            "total": total,
            "parallel": parallel,
            "message": f"Starting cleanup for {total} videos with {parallel} parallel workers"
        })

        if total == 0:
            yield sse_message("complete", {
                "total": 0,
                "completed": 0,
                "skipped": 0,
                "failed": 0,
                "message": "No videos to process"
            })
            return

        # Send initial processing status for first N videos
        processing_videos = videos_data[:parallel]
        for vd in processing_videos:
            yield sse_message("progress", {
                "current": processed + 1,
                "total": total,
                "video_id": vd["video_id"],
                "title": vd["video_title"],
                "status": "processing",
                "message": f"Cleaning transcript ({vd['char_count']} chars)...",
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
            })

        # Process videos in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all tasks
            future_to_video = {
                executor.submit(
                    _process_cleanup_video,
                    vd["video_id"],
                    vd["video_title"],
                    vd["video_description"],
                    vd["video_tags"],
                    vd["transcript_content"],
                    language,
                    preserve_timestamps,
                    settings.openai_api_key,
                ): vd
                for vd in videos_data
            }

            # Process results as they complete
            for future in as_completed(future_to_video):
                vd = future_to_video[future]
                processed += 1

                try:
                    result = future.result()
                    status = result.get("status", "failed")

                    if status == "done":
                        completed += 1
                    elif status == "skipped":
                        skipped += 1
                    else:
                        failed += 1

                    yield sse_message("progress", {
                        "current": processed,
                        "total": total,
                        "video_id": result.get("video_id", vd["video_id"]),
                        "title": result.get("title", vd["video_title"]),
                        "status": status,
                        "message": result.get("message", ""),
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing {vd['video_id']}: {e}")
                    yield sse_message("progress", {
                        "current": processed,
                        "total": total,
                        "video_id": vd["video_id"],
                        "title": vd["video_title"],
                        "status": "failed",
                        "message": str(e)[:100],
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

                # Small delay to allow SSE to flush
                await asyncio.sleep(0.01)

        yield sse_message("complete", {
            "total": total,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "message": f"Batch complete: {completed} cleaned, {skipped} skipped, {failed} failed"
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/upload/candidates")
def get_upload_candidates(
    language: str = Query("fa", description="Language code to check"),
    check_youtube: bool = Query(False, description="Check YouTube for existing captions (costs 50 quota units per video)"),
    db: Session = Depends(get_db),
):
    """Get videos that have transcripts ready for YouTube upload.

    By default, shows ALL videos with transcripts (whisper or cleaned).
    Set check_youtube=true to filter out videos that already have captions on YouTube
    (warning: this costs 50 quota units per video).
    """
    from app.services.youtube_captions import YouTubeCaptionService

    caption_service = None
    if check_youtube:
        try:
            caption_service = YouTubeCaptionService()
            if not caption_service.is_authenticated():
                return {
                    "error": "YouTube not authenticated (needed for check_youtube=true)",
                    "candidates": [],
                    "already_done": [],
                    "summary": {
                        "total_candidates": 0,
                        "already_done": 0,
                        "estimated_total_cost": 0,
                    }
                }
        except Exception as e:
            return {
                "error": str(e),
                "candidates": [],
                "already_done": [],
                "summary": {
                    "total_candidates": 0,
                    "already_done": 0,
                    "estimated_total_cost": 0,
                }
            }

    # Get all videos with whisper or cleaned transcripts
    videos = db.query(Video).filter(Video.sync_status == "synced").all()

    candidates = []
    already_done = []

    for video in videos:
        # Get best transcript (prefer cleaned, then whisper)
        transcript = (
            db.query(Transcript)
            .filter(Transcript.video_id == video.id)
            .filter(Transcript.source.in_(["cleaned", "whisper"]))
            .order_by((Transcript.source == "cleaned").desc())
            .first()
        )

        if not transcript:
            continue  # No transcript to upload

        # Only check YouTube if requested (expensive!)
        has_upload = False
        if check_youtube and caption_service:
            try:
                captions = caption_service.list_captions(video.id)
                has_upload = any(
                    cap.get("language") == language and cap.get("track_kind") != "ASR"
                    for cap in captions
                )
            except Exception as e:
                logger.warning(f"Failed to check captions for {video.id}: {e}")
                has_upload = False

        if has_upload:
            already_done.append({
                "id": video.id,
                "title": video.title,
            })
        else:
            candidates.append({
                "id": video.id,
                "title": video.title,
                "duration_seconds": video.duration_seconds,
                "source": transcript.source,
                "char_count": len(transcript.raw_content),
                "estimated_cost": 0,  # Upload is free (400 quota units though)
            })

    return {
        "candidates": candidates,
        "already_done": already_done,
        "summary": {
            "total_candidates": len(candidates),
            "already_done": len(already_done),
            "estimated_total_cost": 0,
            "note": "Shows all videos with transcripts. Use check_youtube=true to filter already uploaded (costs quota)." if not check_youtube else None,
        }
    }


def _process_youtube_upload(
    video_id: str,
    video_title: str,
    transcript_content: str,
    language: str,
    skip_existing_check: bool = True,
) -> dict:
    """
    Upload transcript to YouTube for a single video.
    This function runs in a thread pool for parallel execution.

    Args:
        skip_existing_check: If True, skip checking for existing captions (saves ~100 quota units)
    """
    from app.services.youtube_captions import YouTubeCaptionService

    try:
        caption_service = YouTubeCaptionService()

        if not caption_service.is_authenticated():
            return {
                "video_id": video_id,
                "title": video_title,
                "status": "failed",
                "message": "YouTube not authenticated",
            }

        # Upload caption directly (skip_check=True saves quota)
        # YouTube will replace if caption already exists with same language
        caption_service.upload_caption(
            video_id=video_id,
            transcript=transcript_content,
            language=language,
            name=f"Whisper ({language})",
            replace_existing=False,  # Don't try to delete first
            skip_check=True,  # Skip list_captions call (saves 50 units)
        )

        return {
            "video_id": video_id,
            "title": video_title,
            "status": "done",
            "message": "Uploaded to YouTube",
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error uploading caption for {video_id}: {e}")

        # Check if it's a duplicate error (caption already exists)
        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
            return {
                "video_id": video_id,
                "title": video_title,
                "status": "skipped",
                "message": "Caption already exists on YouTube",
            }

        return {
            "video_id": video_id,
            "title": video_title,
            "status": "failed",
            "message": error_msg[:100],
        }


@router.get("/upload/run")
async def batch_upload(
    video_ids: Optional[str] = Query(None, description="Comma-separated video IDs, or empty for all candidates"),
    language: str = Query("fa", description="Language code"),
    parallel: int = Query(DEFAULT_PARALLEL_WORKERS, description="Number of parallel workers (1-4)", ge=1, le=4),
    db: Session = Depends(get_db),
):
    """Upload transcripts to YouTube for multiple videos with SSE progress updates."""
    from app.services.youtube_captions import YouTubeCaptionService

    # Check YouTube authentication
    try:
        caption_service = YouTubeCaptionService()
        if not caption_service.is_authenticated():
            async def error_stream():
                yield sse_message("error", {"message": "YouTube not authenticated. Please authenticate first."})
            return StreamingResponse(error_stream(), media_type="text/event-stream")
    except Exception as e:
        async def error_stream():
            yield sse_message("error", {"message": f"YouTube service error: {str(e)}"})
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Determine which videos to process
    if video_ids:
        ids = [id.strip() for id in video_ids.split(",")]
        videos_data = []
        for vid in ids:
            video = db.query(Video).filter(Video.id == vid).first()
            if video:
                transcript = (
                    db.query(Transcript)
                    .filter(Transcript.video_id == vid)
                    .filter(Transcript.source.in_(["cleaned", "whisper"]))
                    .order_by((Transcript.source == "cleaned").desc())
                    .first()
                )
                if transcript:
                    videos_data.append({
                        "video_id": video.id,
                        "video_title": video.title,
                        "transcript_content": transcript.raw_content,
                    })
    else:
        # Get all candidates
        all_videos = db.query(Video).filter(Video.sync_status == "synced").all()
        videos_data = []
        for video in all_videos:
            transcript = (
                db.query(Transcript)
                .filter(Transcript.video_id == video.id)
                .filter(Transcript.source.in_(["cleaned", "whisper"]))
                .order_by((Transcript.source == "cleaned").desc())
                .first()
            )
            if transcript:
                videos_data.append({
                    "video_id": video.id,
                    "video_title": video.title,
                    "transcript_content": transcript.raw_content,
                })

    async def generate():
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(videos_data)
        completed = 0
        skipped = 0
        failed = 0
        processed = 0

        yield sse_message("start", {
            "total": total,
            "parallel": parallel,
            "message": f"Starting YouTube upload for {total} videos with {parallel} parallel workers"
        })

        if total == 0:
            yield sse_message("complete", {
                "total": 0,
                "completed": 0,
                "skipped": 0,
                "failed": 0,
                "message": "No videos to upload"
            })
            return

        # Send initial processing status
        for vd in videos_data[:parallel]:
            yield sse_message("progress", {
                "current": processed + 1,
                "total": total,
                "video_id": vd["video_id"],
                "title": vd["video_title"],
                "status": "processing",
                "message": "Uploading to YouTube...",
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
            })

        # Process videos in parallel
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            future_to_video = {
                executor.submit(
                    _process_youtube_upload,
                    vd["video_id"],
                    vd["video_title"],
                    vd["transcript_content"],
                    language,
                ): vd
                for vd in videos_data
            }

            for future in as_completed(future_to_video):
                vd = future_to_video[future]
                processed += 1

                try:
                    result = future.result()
                    status = result.get("status", "failed")

                    if status == "done":
                        completed += 1
                    elif status == "skipped":
                        skipped += 1
                    else:
                        failed += 1

                    yield sse_message("progress", {
                        "current": processed,
                        "total": total,
                        "video_id": result.get("video_id", vd["video_id"]),
                        "title": result.get("title", vd["video_title"]),
                        "status": status,
                        "message": result.get("message", ""),
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

                except Exception as e:
                    failed += 1
                    logger.error(f"Error uploading {vd['video_id']}: {e}")
                    yield sse_message("progress", {
                        "current": processed,
                        "total": total,
                        "video_id": vd["video_id"],
                        "title": vd["video_title"],
                        "status": "failed",
                        "message": str(e)[:100],
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                    })

                await asyncio.sleep(0.01)

        yield sse_message("complete", {
            "total": total,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "message": f"Batch complete: {completed} uploaded, {skipped} skipped, {failed} failed"
        })

    return StreamingResponse(generate(), media_type="text/event-stream")
