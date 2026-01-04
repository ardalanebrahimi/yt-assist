"""YouTube Caption Upload Service using OAuth 2.0."""

import io
import logging
import os
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

# OAuth 2.0 scopes required for caption management
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
]

# Token and credentials paths
DATA_DIR = Path("data")
TOKEN_PATH = DATA_DIR / "youtube_token.json"
CREDENTIALS_PATH = DATA_DIR / "client_secrets.json"


class YouTubeCaptionService:
    """Service for uploading captions to YouTube using OAuth 2.0."""

    def __init__(self, credentials_path: str = None, token_path: str = None):
        """Initialize the YouTube Caption Service.

        Args:
            credentials_path: Path to OAuth client_secrets.json
            token_path: Path to store/load the token
        """
        self.credentials_path = Path(credentials_path) if credentials_path else CREDENTIALS_PATH
        self.token_path = Path(token_path) if token_path else TOKEN_PATH
        self._youtube = None
        self._credentials = None

    def _get_credentials(self) -> Optional[Credentials]:
        """Get or refresh OAuth credentials.

        Returns:
            Valid credentials or None if authentication fails
        """
        credentials = None

        # Load existing token
        if self.token_path.exists():
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")

        # If no valid credentials, authenticate
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                except Exception as e:
                    logger.warning(f"Failed to refresh token: {e}")
                    credentials = None

            if not credentials:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth credentials file not found: {self.credentials_path}\n"
                        "Download from Google Cloud Console > Credentials > OAuth 2.0 Client IDs"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                credentials = flow.run_local_server(port=0)

            # Save token for future use
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as token_file:
                token_file.write(credentials.to_json())

        return credentials

    def _get_youtube_service(self):
        """Get authenticated YouTube API service.

        Returns:
            YouTube API service object
        """
        if self._youtube is None:
            credentials = self._get_credentials()
            if not credentials:
                raise RuntimeError("Failed to get OAuth credentials")
            self._youtube = build("youtube", "v3", credentials=credentials)
        return self._youtube

    def is_authenticated(self) -> bool:
        """Check if we have valid authentication.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            self._get_credentials()
            return True
        except Exception:
            return False

    def list_captions(self, video_id: str) -> list[dict]:
        """List existing captions for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            List of caption track information
        """
        try:
            youtube = self._get_youtube_service()
            response = youtube.captions().list(
                part="snippet",
                videoId=video_id,
            ).execute()

            captions = []
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                captions.append({
                    "id": item.get("id"),
                    "language": snippet.get("language"),
                    "name": snippet.get("name"),
                    "is_auto_synced": snippet.get("isAutoSynced"),
                    "is_draft": snippet.get("isDraft"),
                    "track_kind": snippet.get("trackKind"),
                })
            return captions
        except Exception as e:
            logger.error(f"Error listing captions for {video_id}: {e}")
            raise

    def upload_caption(
        self,
        video_id: str,
        transcript: str,
        language: str = "fa",
        name: str = "",
        is_draft: bool = False,
        replace_existing: bool = True,
        skip_check: bool = False,
    ) -> dict:
        """Upload a caption track to YouTube.

        Args:
            video_id: YouTube video ID
            transcript: Transcript text with timestamps in [MM:SS] format
            language: Language code (e.g., "fa" for Persian)
            name: Caption track name (optional)
            is_draft: Whether to save as draft
            replace_existing: Delete existing caption with same language/name first
            skip_check: Skip checking for existing captions (saves 50 quota units)

        Returns:
            Caption track information
        """
        try:
            youtube = self._get_youtube_service()
            caption_name = name or f"Whisper ({language})"

            # Delete existing caption if replace_existing is True (unless skip_check)
            if replace_existing and not skip_check:
                existing = self.list_captions(video_id)
                for cap in existing:
                    if cap.get("language") == language and cap.get("name") == caption_name:
                        logger.info(f"Deleting existing caption: {cap.get('id')}")
                        self.delete_caption(cap.get("id"))
                        break

            # Convert transcript to SRT format
            srt_content = self._convert_to_srt(transcript)

            # Create caption resource
            caption_body = {
                "snippet": {
                    "videoId": video_id,
                    "language": language,
                    "name": caption_name,
                    "isDraft": is_draft,
                }
            }

            # Upload caption content as SRT
            caption_bytes = srt_content.encode("utf-8")
            media = MediaIoBaseUpload(
                io.BytesIO(caption_bytes),
                mimetype="application/x-subrip",
                resumable=True,
            )

            response = youtube.captions().insert(
                part="snippet",
                body=caption_body,
                media_body=media,
            ).execute()

            logger.info(f"Uploaded caption for video {video_id}: {response.get('id')}")

            return {
                "id": response.get("id"),
                "language": response.get("snippet", {}).get("language"),
                "name": response.get("snippet", {}).get("name"),
                "video_id": video_id,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error uploading caption for {video_id}: {e}")
            raise

    def _convert_to_srt(self, transcript: str) -> str:
        """Convert transcript with [MM:SS] timestamps to SRT format.

        Args:
            transcript: Transcript with lines like "[00:00] Text here"

        Returns:
            SRT formatted string
        """
        import re

        lines = transcript.strip().split("\n")
        srt_entries = []
        index = 1

        # Pattern to match timestamps like [00:00] or [00:00:00]
        timestamp_pattern = re.compile(r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*(.*)")

        for i, line in enumerate(lines):
            match = timestamp_pattern.match(line.strip())
            if match:
                groups = match.groups()
                if groups[2]:  # HH:MM:SS format
                    hours = int(groups[0])
                    minutes = int(groups[1])
                    seconds = int(groups[2])
                else:  # MM:SS format
                    hours = 0
                    minutes = int(groups[0])
                    seconds = int(groups[1])

                text = groups[3].strip()
                if not text:
                    continue

                # Calculate start time
                start_total_seconds = hours * 3600 + minutes * 60 + seconds

                # Find end time (next timestamp or +5 seconds)
                end_total_seconds = start_total_seconds + 5  # Default 5 second duration
                for j in range(i + 1, len(lines)):
                    next_match = timestamp_pattern.match(lines[j].strip())
                    if next_match:
                        next_groups = next_match.groups()
                        if next_groups[2]:
                            end_total_seconds = int(next_groups[0]) * 3600 + int(next_groups[1]) * 60 + int(next_groups[2])
                        else:
                            end_total_seconds = int(next_groups[0]) * 60 + int(next_groups[1])
                        break

                # Format times as SRT timestamps (HH:MM:SS,mmm)
                start_time = self._seconds_to_srt_time(start_total_seconds)
                end_time = self._seconds_to_srt_time(end_total_seconds)

                srt_entries.append(f"{index}\n{start_time} --> {end_time}\n{text}\n")
                index += 1

        return "\n".join(srt_entries)

    @staticmethod
    def _seconds_to_srt_time(seconds: int) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},000"

    def delete_caption(self, caption_id: str) -> bool:
        """Delete a caption track.

        Args:
            caption_id: Caption track ID

        Returns:
            True if deleted successfully
        """
        try:
            youtube = self._get_youtube_service()
            youtube.captions().delete(id=caption_id).execute()
            logger.info(f"Deleted caption: {caption_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting caption {caption_id}: {e}")
            raise

    def update_caption(
        self,
        caption_id: str,
        transcript: str,
        is_draft: bool = None,
    ) -> dict:
        """Update an existing caption track.

        Args:
            caption_id: Caption track ID
            transcript: New transcript text
            is_draft: Whether to mark as draft (optional)

        Returns:
            Updated caption information
        """
        try:
            youtube = self._get_youtube_service()

            # Prepare update body
            caption_body = {"id": caption_id}
            if is_draft is not None:
                caption_body["snippet"] = {"isDraft": is_draft}

            # Upload new content
            caption_bytes = transcript.encode("utf-8")
            media = MediaIoBaseUpload(
                io.BytesIO(caption_bytes),
                mimetype="text/plain",
                resumable=True,
            )

            response = youtube.captions().update(
                part="snippet",
                body=caption_body,
                media_body=media,
            ).execute()

            logger.info(f"Updated caption: {caption_id}")

            return {
                "id": response.get("id"),
                "language": response.get("snippet", {}).get("language"),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error updating caption {caption_id}: {e}")
            raise
