"""Sync service for orchestrating video and transcript synchronization."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Video, Transcript
from app.services.youtube import YouTubeService, VideoMetadata
from app.services.transcripts import TranscriptService

logger = logging.getLogger(__name__)


@dataclass
class SyncStatus:
    """Summary of sync status."""

    total_videos: int
    synced: int
    pending: int
    errors: int


@dataclass
class SyncResult:
    """Result of a sync operation."""

    video_id: str
    success: bool
    error: Optional[str] = None
    has_transcript: bool = False


class SyncService:
    """Service for synchronizing YouTube channel data."""

    def __init__(
        self,
        db: Session,
        youtube_service: Optional[YouTubeService] = None,
        transcript_service: Optional[TranscriptService] = None,
    ):
        """Initialize sync service with dependencies."""
        self.db = db
        self.youtube = youtube_service or YouTubeService()
        self.transcript = transcript_service or TranscriptService()
        self.settings = get_settings()

    def sync_all_videos(self, channel_id: Optional[str] = None) -> list[SyncResult]:
        """
        Sync all videos from a channel.

        Args:
            channel_id: YouTube channel ID (defaults to configured channel)

        Returns:
            List of SyncResult for each video
        """
        channel_id = channel_id or self.settings.channel_id
        results: list[SyncResult] = []

        logger.info(f"Starting full sync for channel {channel_id}")

        # Fetch all videos from YouTube
        try:
            video_metadata_list = self.youtube.get_channel_videos(channel_id)
        except Exception as e:
            logger.error(f"Failed to fetch videos from YouTube: {e}")
            return results

        logger.info(f"Found {len(video_metadata_list)} videos to sync")

        # Sync each video
        for metadata in video_metadata_list:
            result = self._sync_video(metadata)
            results.append(result)

        # Commit all changes
        self.db.commit()

        # Log summary
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Sync complete: {success_count}/{len(results)} videos synced successfully")

        return results

    def sync_single_video(self, video_id: str) -> SyncResult:
        """
        Sync a single video by ID.

        Args:
            video_id: YouTube video ID

        Returns:
            SyncResult for the video
        """
        logger.info(f"Syncing single video: {video_id}")

        # Fetch video metadata from YouTube
        metadata = self.youtube.get_video(video_id)
        if not metadata:
            return SyncResult(
                video_id=video_id,
                success=False,
                error="Video not found on YouTube",
            )

        result = self._sync_video(metadata)
        self.db.commit()

        return result

    def _sync_video(self, metadata: VideoMetadata) -> SyncResult:
        """Internal method to sync a single video."""
        video_id = metadata.id

        try:
            # Create or update video record
            video = self.db.query(Video).filter(Video.id == video_id).first()

            if video is None:
                video = Video(id=video_id)
                self.db.add(video)

            # Update video metadata
            video.title = metadata.title
            video.description = metadata.description
            video.published_at = metadata.published_at
            video.duration_seconds = metadata.duration_seconds
            video.tags = metadata.tags
            video.thumbnail_url = metadata.thumbnail_url
            video.channel_id = metadata.channel_id
            video.view_count = metadata.view_count
            video.updated_at = datetime.utcnow()

            # Fetch transcript
            transcript_result = self.transcript.fetch_transcript(video_id)

            has_transcript = False
            if transcript_result:
                # Check if transcript already exists
                existing = (
                    self.db.query(Transcript)
                    .filter(
                        Transcript.video_id == video_id,
                        Transcript.language_code == transcript_result.language_code,
                    )
                    .first()
                )

                if existing:
                    # Update existing transcript
                    existing.is_auto_generated = transcript_result.is_auto_generated
                    existing.raw_content = transcript_result.raw_content
                    existing.clean_content = transcript_result.clean_content
                else:
                    # Create new transcript
                    transcript = Transcript(
                        video_id=video_id,
                        language_code=transcript_result.language_code,
                        is_auto_generated=transcript_result.is_auto_generated,
                        raw_content=transcript_result.raw_content,
                        clean_content=transcript_result.clean_content,
                    )
                    self.db.add(transcript)

                has_transcript = True

            # Update sync status
            video.sync_status = "synced"
            video.sync_error = None
            video.synced_at = datetime.utcnow()

            return SyncResult(
                video_id=video_id,
                success=True,
                has_transcript=has_transcript,
            )

        except Exception as e:
            logger.error(f"Error syncing video {video_id}: {e}")

            # Update video with error status if it exists
            video = self.db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.sync_status = "error"
                video.sync_error = str(e)

            return SyncResult(
                video_id=video_id,
                success=False,
                error=str(e),
            )

    def get_sync_status(self) -> SyncStatus:
        """Get summary of sync status across all videos."""
        total = self.db.query(Video).count()
        synced = self.db.query(Video).filter(Video.sync_status == "synced").count()
        pending = self.db.query(Video).filter(Video.sync_status == "pending").count()
        errors = self.db.query(Video).filter(Video.sync_status == "error").count()

        return SyncStatus(
            total_videos=total,
            synced=synced,
            pending=pending,
            errors=errors,
        )

    def get_videos_needing_sync(self) -> list[Video]:
        """Get all videos that need syncing (pending or error status)."""
        return (
            self.db.query(Video)
            .filter(Video.sync_status.in_(["pending", "error"]))
            .all()
        )
