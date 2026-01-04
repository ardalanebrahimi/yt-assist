"""YouTube Data API v3 client for fetching channel videos."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Video metadata from YouTube API."""

    id: str
    title: str
    description: str
    published_at: datetime
    duration_seconds: int
    tags: list[str]
    thumbnail_url: str
    channel_id: str
    view_count: Optional[int] = None
    live_broadcast_content: Optional[str] = None  # "live", "upcoming", or "none"


class YouTubeService:
    """Service for interacting with YouTube Data API v3."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube service with API key."""
        settings = get_settings()
        self.api_key = api_key or settings.youtube_api_key
        if not self.api_key:
            raise ValueError("YouTube API key is required. Set YOUTUBE_API_KEY in .env")
        self._youtube = build("youtube", "v3", developerKey=self.api_key)

    def get_channel_videos(
        self, channel_id: str, include_live: bool = True
    ) -> list[VideoMetadata]:
        """
        Fetch all videos from a YouTube channel.

        Args:
            channel_id: YouTube channel ID (e.g., UCmHxUdpnCfQTQtwbxN9mtOA)
            include_live: Whether to include live/upcoming broadcasts

        Returns:
            List of VideoMetadata objects
        """
        videos: list[VideoMetadata] = []
        video_ids: set[str] = set()

        # Step 1: Get uploads playlist ID from channel
        uploads_playlist_id = self._get_uploads_playlist_id(channel_id)
        if not uploads_playlist_id:
            logger.warning(f"Could not find uploads playlist for channel {channel_id}")
            return videos

        # Step 2: Get all video IDs from uploads playlist (paginated)
        next_page_token = None
        while True:
            request = self._youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            response = request.execute()

            for item in response.get("items", []):
                video_id = item["contentDetails"]["videoId"]
                video_ids.add(video_id)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        logger.info(f"Found {len(video_ids)} videos in uploads playlist")

        # Step 2b: Also fetch live/upcoming broadcasts (not in uploads playlist)
        if include_live:
            live_ids = self._get_live_broadcast_ids(channel_id)
            if live_ids:
                logger.info(f"Found {len(live_ids)} live/upcoming broadcasts")
                video_ids.update(live_ids)

        logger.info(f"Total {len(video_ids)} videos for channel {channel_id}")

        # Step 3: Fetch full video details in batches of 50
        video_ids_list = list(video_ids)
        for i in range(0, len(video_ids_list), 50):
            batch_ids = video_ids_list[i : i + 50]
            batch_videos = self._get_videos_details(batch_ids, channel_id)
            videos.extend(batch_videos)

        return videos

    def _get_live_broadcast_ids(self, channel_id: str) -> list[str]:
        """Fetch live and upcoming broadcast video IDs for a channel."""
        video_ids = []

        # Search for live and upcoming broadcasts
        for event_type in ["live", "upcoming"]:
            try:
                request = self._youtube.search().list(
                    part="id",
                    channelId=channel_id,
                    eventType=event_type,
                    type="video",
                    maxResults=50,
                )
                response = request.execute()

                for item in response.get("items", []):
                    video_id = item["id"].get("videoId")
                    if video_id:
                        video_ids.append(video_id)

            except HttpError as e:
                logger.warning(f"Error fetching {event_type} broadcasts: {e}")

        return video_ids

    def get_video(self, video_id: str) -> Optional[VideoMetadata]:
        """
        Fetch a single video's metadata.

        Args:
            video_id: YouTube video ID

        Returns:
            VideoMetadata or None if not found
        """
        videos = self._get_videos_details([video_id], channel_id="")
        return videos[0] if videos else None

    def _get_uploads_playlist_id(self, channel_id: str) -> Optional[str]:
        """Get the uploads playlist ID for a channel."""
        try:
            request = self._youtube.channels().list(
                part="contentDetails",
                id=channel_id,
            )
            response = request.execute()

            items = response.get("items", [])
            if not items:
                return None

            return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        except HttpError as e:
            logger.error(f"Error fetching channel {channel_id}: {e}")
            return None

    def _get_videos_details(
        self, video_ids: list[str], channel_id: str
    ) -> list[VideoMetadata]:
        """Fetch detailed metadata for a batch of videos."""
        if not video_ids:
            return []

        try:
            request = self._youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(video_ids),
            )
            response = request.execute()

            videos = []
            for item in response.get("items", []):
                video = self._parse_video_response(item, channel_id)
                if video:
                    videos.append(video)

            return videos
        except HttpError as e:
            logger.error(f"Error fetching video details: {e}")
            return []

    def _parse_video_response(
        self, item: dict, default_channel_id: str
    ) -> Optional[VideoMetadata]:
        """Parse YouTube API response into VideoMetadata."""
        try:
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})

            # Parse duration (ISO 8601 format: PT1H2M3S)
            duration_str = content_details.get("duration", "PT0S")
            duration_seconds = self._parse_duration(duration_str)

            # Parse published date
            published_str = snippet.get("publishedAt", "")
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

            # Get best thumbnail
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("maxres", {}).get("url")
                or thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url", "")
            )

            # Parse view count
            view_count = None
            if "viewCount" in statistics:
                view_count = int(statistics["viewCount"])

            return VideoMetadata(
                id=item["id"],
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                published_at=published_at,
                duration_seconds=duration_seconds,
                tags=snippet.get("tags", []),
                thumbnail_url=thumbnail_url,
                channel_id=snippet.get("channelId", default_channel_id),
                view_count=view_count,
                live_broadcast_content=snippet.get("liveBroadcastContent"),
            )
        except Exception as e:
            logger.error(f"Error parsing video {item.get('id')}: {e}")
            return None

    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """
        Parse ISO 8601 duration to seconds.

        Examples: PT1H2M3S -> 3723, PT5M -> 300, PT30S -> 30
        """
        import re

        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds
