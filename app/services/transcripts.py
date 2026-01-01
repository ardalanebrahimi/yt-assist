"""Transcript fetching and cleaning service using youtube-transcript-api."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

# Create a single instance of the API
_youtube_transcript_api = YouTubeTranscriptApi()


@dataclass
class TranscriptSegment:
    """A single segment of a transcript with timing."""

    text: str
    start: float  # Start time in seconds
    duration: float  # Duration in seconds


@dataclass
class TranscriptResult:
    """Result of transcript fetching."""

    video_id: str
    language_code: str
    is_auto_generated: bool
    segments: list[TranscriptSegment]
    raw_content: str  # Original with timestamps
    clean_content: str  # Plain text


class TranscriptService:
    """Service for fetching and processing YouTube transcripts."""

    # Preferred languages in order of priority (Persian variants + English)
    PREFERRED_LANGUAGES = ["fa", "fa-IR", "per", "fas", "en", "en-US", "en-GB"]

    def fetch_transcript(self, video_id: str) -> Optional[TranscriptResult]:
        """
        Fetch transcript for a video.

        Tries to get manual captions first, falls back to auto-generated.

        Args:
            video_id: YouTube video ID

        Returns:
            TranscriptResult or None if no transcript available
        """
        try:
            transcript_list = _youtube_transcript_api.list(video_id)

            # Try to find a manually created transcript first
            transcript = self._find_best_transcript(transcript_list, manual_first=True)

            if transcript is None:
                logger.warning(f"No transcript found for video {video_id}")
                return None

            # Fetch the transcript data
            transcript_data = transcript.fetch()

            # Build segments (new API returns objects with attributes, not dicts)
            segments = [
                TranscriptSegment(
                    text=entry.text,
                    start=entry.start,
                    duration=entry.duration,
                )
                for entry in transcript_data
            ]

            # Generate raw and clean content
            raw_content = self._build_raw_content(segments)
            clean_content = self._build_clean_content(segments)

            return TranscriptResult(
                video_id=video_id,
                language_code=transcript.language_code,
                is_auto_generated=transcript.is_generated,
                segments=segments,
                raw_content=raw_content,
                clean_content=clean_content,
            )

        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video {video_id}")
            return None
        except VideoUnavailable:
            logger.warning(f"Video {video_id} is unavailable")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return None

    def _find_best_transcript(self, transcript_list, manual_first: bool = True):
        """Find the best available transcript based on preferences."""
        # Collect all available transcripts
        all_transcripts = []
        manual_transcripts = []
        auto_transcripts = []

        try:
            for transcript in transcript_list:
                all_transcripts.append(transcript)
                logger.info(
                    f"Found transcript: lang={transcript.language_code}, "
                    f"auto={transcript.is_generated}"
                )
                if transcript.is_generated:
                    auto_transcripts.append(transcript)
                else:
                    manual_transcripts.append(transcript)
        except Exception as e:
            logger.warning(f"Error iterating transcripts: {e}")

        # Determine search order
        if manual_first:
            search_order = [manual_transcripts, auto_transcripts]
        else:
            search_order = [auto_transcripts, manual_transcripts]

        # Search for preferred languages in order
        for transcripts in search_order:
            for lang in self.PREFERRED_LANGUAGES:
                for transcript in transcripts:
                    lang_code = transcript.language_code.lower()
                    if lang_code.startswith(lang.lower().split("-")[0]):
                        logger.info(f"Selected transcript: {transcript.language_code}")
                        return transcript

            # If no preferred language, return first available from this category
            if transcripts:
                logger.info(f"Using first available: {transcripts[0].language_code}")
                return transcripts[0]

        # Last resort: return ANY available transcript
        if all_transcripts:
            logger.info(f"Fallback to any transcript: {all_transcripts[0].language_code}")
            return all_transcripts[0]

        # Try the built-in methods as final fallback
        try:
            return transcript_list.find_transcript(self.PREFERRED_LANGUAGES)
        except Exception:
            pass

        try:
            return transcript_list.find_generated_transcript(self.PREFERRED_LANGUAGES)
        except Exception:
            pass

        return None

    def _build_raw_content(self, segments: list[TranscriptSegment]) -> str:
        """Build raw content with timestamps."""
        lines = []
        for seg in segments:
            timestamp = self._format_timestamp(seg.start)
            lines.append(f"[{timestamp}] {seg.text}")
        return "\n".join(lines)

    def _build_clean_content(self, segments: list[TranscriptSegment]) -> str:
        """Build clean content without timestamps, properly merged."""
        # Join all text
        full_text = " ".join(seg.text for seg in segments)

        # Clean up the text
        clean_text = self._clean_text(full_text)

        return clean_text

    def _clean_text(self, text: str) -> str:
        """Clean transcript text."""
        # Remove multiple spaces
        text = re.sub(r"\s+", " ", text)

        # Remove common transcript artifacts
        text = re.sub(r"\[Music\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[Applause\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[Laughter\]", "", text, flags=re.IGNORECASE)

        # Remove extra whitespace
        text = text.strip()

        # Fix spacing around punctuation
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)

        return text

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
