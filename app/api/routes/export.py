"""Export endpoints for transcripts."""

import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Video, Transcript

router = APIRouter()


@router.get("/jsonl")
def export_jsonl(db: Session = Depends(get_db)):
    """
    Export all transcripts as JSONL (JSON Lines) format.

    Each line contains video metadata and transcript.
    """
    videos = (
        db.query(Video)
        .filter(Video.sync_status == "synced")
        .order_by(Video.published_at.desc())
        .all()
    )

    def generate_jsonl():
        for video in videos:
            for transcript in video.transcripts:
                record = {
                    "video_id": video.id,
                    "title": video.title,
                    "description": video.description,
                    "published_at": video.published_at.isoformat() if video.published_at else None,
                    "duration_seconds": video.duration_seconds,
                    "tags": video.tags or [],
                    "channel_id": video.channel_id,
                    "language_code": transcript.language_code,
                    "is_auto_generated": transcript.is_auto_generated,
                    "transcript": transcript.raw_content,  # With timestamps
                    "transcript_clean": transcript.clean_content,  # Plain text
                }
                yield json.dumps(record, ensure_ascii=False) + "\n"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcripts_{timestamp}.jsonl"

    return StreamingResponse(
        generate_jsonl(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/zip")
def export_zip(db: Session = Depends(get_db)):
    """
    Export all transcripts as a ZIP file with individual text files.

    Each video gets a text file named: {video_id}_{sanitized_title}.txt
    """
    videos = (
        db.query(Video)
        .filter(Video.sync_status == "synced")
        .order_by(Video.published_at.desc())
        .all()
    )

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add metadata JSON
        metadata = []
        for video in videos:
            metadata.append({
                "video_id": video.id,
                "title": video.title,
                "published_at": video.published_at.isoformat() if video.published_at else None,
                "duration_seconds": video.duration_seconds,
                "tags": video.tags or [],
                "has_transcript": len(video.transcripts) > 0,
            })
        zip_file.writestr(
            "metadata.json",
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )

        # Add transcript files
        for video in videos:
            for transcript in video.transcripts:
                # Sanitize filename
                safe_title = "".join(
                    c if c.isalnum() or c in " -_" else "_"
                    for c in video.title[:50]
                ).strip()
                filename = f"{video.id}_{safe_title}.txt"

                # Build content with header
                content = f"""Title: {video.title}
Video ID: {video.id}
Published: {video.published_at.strftime('%Y-%m-%d') if video.published_at else 'Unknown'}
Language: {transcript.language_code}
Auto-generated: {transcript.is_auto_generated}

---

{transcript.raw_content}
"""
                zip_file.writestr(f"transcripts/{filename}", content)

    zip_buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcripts_{timestamp}.zip"

    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/stats")
def export_stats(db: Session = Depends(get_db)):
    """Get export statistics."""
    total_videos = db.query(Video).count()
    synced_videos = db.query(Video).filter(Video.sync_status == "synced").count()
    total_transcripts = db.query(Transcript).count()

    # Calculate total words
    total_words = 0
    transcripts = db.query(Transcript).all()
    for t in transcripts:
        total_words += len(t.clean_content.split())

    return {
        "total_videos": total_videos,
        "synced_videos": synced_videos,
        "total_transcripts": total_transcripts,
        "total_words": total_words,
        "exportable": synced_videos > 0,
    }
