"""Whisper transcription service using OpenAI API."""

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yt_dlp
from openai import OpenAI

from app.config import get_settings

# Path to Whisper config file
WHISPER_CONFIG_PATH = Path("data/whisper_config.json")


def load_whisper_config() -> dict:
    """Load Whisper configuration from JSON file."""
    if WHISPER_CONFIG_PATH.exists():
        try:
            with open(WHISPER_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# Lazy import pydub - only needed for chunking large files
# pydub has issues with Python 3.13+ due to audioop removal
AudioSegment = None
def _get_audio_segment():
    global AudioSegment
    if AudioSegment is None:
        try:
            from pydub import AudioSegment as AS
            AudioSegment = AS
        except ImportError as e:
            raise ImportError(
                "pydub is required for chunking large audio files. "
                "Install with: pip install pydub\n"
                "Note: Python 3.13+ may have compatibility issues."
            ) from e
    return AudioSegment

logger = logging.getLogger(__name__)

# Maximum file size for Whisper API (25 MB)
MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Chunk settings
CHUNK_DURATION_MS = 10 * 60 * 1000  # 10 minutes per chunk
CHUNK_OVERLAP_MS = 10 * 1000  # 10 seconds overlap


@dataclass
class WhisperSegment:
    """A single segment of a Whisper transcript."""

    text: str
    start: float  # Start time in seconds
    end: float  # End time in seconds


@dataclass
class WhisperResult:
    """Result of Whisper transcription."""

    video_id: str
    language_code: str
    segments: list[WhisperSegment]
    raw_content: str  # With timestamps
    clean_content: str  # Plain text


class WhisperService:
    """Service for transcribing YouTube videos using OpenAI Whisper API."""

    def __init__(self, api_key: str = None):
        """Initialize the Whisper service.

        Args:
            api_key: OpenAI API key. If not provided, uses settings.
        """
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required for Whisper service")
        self.client = OpenAI(api_key=self.api_key)
        self.temp_dir = Path(tempfile.gettempdir()) / "yt_assist_whisper"
        self.temp_dir.mkdir(exist_ok=True)
        self.config = load_whisper_config()

    def _get_initial_prompt(self, language: str) -> Optional[str]:
        """Get initial prompt for Whisper based on language and config.

        The initial_prompt helps Whisper recognize expected vocabulary.

        Args:
            language: Language code

        Returns:
            Initial prompt string or None
        """
        prompts = self.config.get("initial_prompts", {})
        return prompts.get(language)

    def transcribe_video(
        self, video_id: str, language: str = "fa"
    ) -> Optional[WhisperResult]:
        """
        Transcribe a YouTube video using Whisper.

        Args:
            video_id: YouTube video ID
            language: Language code for transcription (default: Persian)

        Returns:
            WhisperResult or None if transcription failed
        """
        audio_path = None
        try:
            # Step 1: Download audio
            logger.info(f"Downloading audio for video {video_id}")
            audio_path = self._download_audio(video_id)
            if not audio_path:
                logger.error(f"Failed to download audio for {video_id}")
                return None

            # Step 2: Check file size and chunk if needed
            file_size = os.path.getsize(audio_path)
            logger.info(f"Audio file size: {file_size / 1024 / 1024:.2f} MB")

            if file_size > MAX_FILE_SIZE_BYTES:
                logger.info("File exceeds 25MB, chunking audio...")
                segments = self._transcribe_chunked(audio_path, language)
            else:
                segments = self._transcribe_single(audio_path, language)

            if not segments:
                logger.error(f"No segments returned for {video_id}")
                return None

            # Step 3: Build raw and clean content
            raw_content = self._build_raw_content(segments)
            clean_content = self._build_clean_content(segments)

            return WhisperResult(
                video_id=video_id,
                language_code=language,
                segments=segments,
                raw_content=raw_content,
                clean_content=clean_content,
            )

        except Exception as e:
            logger.error(f"Error transcribing video {video_id}: {e}")
            return None
        finally:
            # Cleanup temp files
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {audio_path}: {e}")

    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg installation path.

        Returns:
            Path to FFmpeg directory or None
        """
        import shutil

        # Check if ffmpeg is in PATH
        if shutil.which("ffmpeg"):
            return None  # Let yt-dlp find it automatically

        # Common Windows installation locations
        common_paths = [
            Path("C:/Program Files/Shotcut"),
            Path("C:/Program Files/ffmpeg/bin"),
            Path("C:/ffmpeg/bin"),
            Path("C:/Program Files/Windows Movie Maker"),
            Path.home() / "AppData/Local/Microsoft/WinGet/Packages",
        ]

        for path in common_paths:
            ffmpeg_exe = path / "ffmpeg.exe"
            if ffmpeg_exe.exists():
                logger.info(f"Found FFmpeg at: {path}")
                return str(path)

        # Search in WinGet packages
        winget_path = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        if winget_path.exists():
            for subdir in winget_path.iterdir():
                if "ffmpeg" in subdir.name.lower():
                    for bin_path in subdir.rglob("ffmpeg.exe"):
                        logger.info(f"Found FFmpeg at: {bin_path.parent}")
                        return str(bin_path.parent)

        logger.warning("FFmpeg not found - transcription may fail")
        return None

    def _download_audio(self, video_id: str) -> Optional[str]:
        """Download audio from YouTube video.

        Args:
            video_id: YouTube video ID

        Returns:
            Path to downloaded audio file or None
        """
        output_path = self.temp_dir / f"{video_id}.mp3"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(self.temp_dir / f"{video_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",  # Lower quality to reduce file size
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": self._find_ffmpeg(),
        }

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if output_path.exists():
                return str(output_path)

            # Check for other possible extensions
            for ext in ["mp3", "m4a", "webm", "opus"]:
                alt_path = self.temp_dir / f"{video_id}.{ext}"
                if alt_path.exists():
                    return str(alt_path)

            return None
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None

    def _transcribe_single(
        self, audio_path: str, language: str
    ) -> list[WhisperSegment]:
        """Transcribe a single audio file (< 25MB).

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of WhisperSegments
        """
        try:
            # Get initial prompt for better vocabulary recognition
            initial_prompt = self._get_initial_prompt(language)

            with open(audio_path, "rb") as audio_file:
                # Build API call parameters
                api_params = {
                    "model": "whisper-1",
                    "file": audio_file,
                    "language": language,
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["segment"],
                }

                # Add initial prompt if configured
                if initial_prompt:
                    api_params["prompt"] = initial_prompt
                    logger.info(f"Using initial prompt for {language}")

                response = self.client.audio.transcriptions.create(**api_params)

            segments = []
            if hasattr(response, "segments") and response.segments:
                for seg in response.segments:
                    segments.append(
                        WhisperSegment(
                            text=getattr(seg, "text", "").strip(),
                            start=getattr(seg, "start", 0),
                            end=getattr(seg, "end", 0),
                        )
                    )
            else:
                # Fallback: create single segment from full text
                segments.append(
                    WhisperSegment(
                        text=response.text.strip(),
                        start=0,
                        end=0,
                    )
                )

            return segments
        except Exception as e:
            logger.error(f"Error in single transcription: {e}")
            return []

    def _transcribe_chunked(
        self, audio_path: str, language: str
    ) -> list[WhisperSegment]:
        """Transcribe a large audio file by chunking.

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of WhisperSegments with adjusted timestamps
        """
        try:
            AudioSegment = _get_audio_segment()
            audio = AudioSegment.from_file(audio_path)
            total_duration_ms = len(audio)
            all_segments = []
            chunk_index = 0

            # Process in chunks
            start_ms = 0
            while start_ms < total_duration_ms:
                end_ms = min(start_ms + CHUNK_DURATION_MS, total_duration_ms)
                chunk = audio[start_ms:end_ms]

                # Export chunk to temp file
                chunk_path = self.temp_dir / f"chunk_{chunk_index}.mp3"
                chunk.export(str(chunk_path), format="mp3", bitrate="128k")

                logger.info(
                    f"Transcribing chunk {chunk_index + 1} "
                    f"({start_ms / 1000:.0f}s - {end_ms / 1000:.0f}s)"
                )

                # Get previous context for better continuity
                prompt = None
                if all_segments:
                    # Use last few segments as context
                    last_text = " ".join(s.text for s in all_segments[-3:])
                    prompt = last_text[-200:]  # Last 200 chars

                # Transcribe chunk
                try:
                    with open(chunk_path, "rb") as audio_file:
                        response = self.client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language=language,
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                            prompt=prompt,
                        )

                    # Adjust timestamps and add segments
                    if hasattr(response, "segments") and response.segments:
                        for seg in response.segments:
                            adjusted_start = start_ms / 1000 + getattr(seg, "start", 0)
                            adjusted_end = start_ms / 1000 + getattr(seg, "end", 0)
                            all_segments.append(
                                WhisperSegment(
                                    text=getattr(seg, "text", "").strip(),
                                    start=adjusted_start,
                                    end=adjusted_end,
                                )
                            )
                    else:
                        # Fallback
                        all_segments.append(
                            WhisperSegment(
                                text=response.text.strip(),
                                start=start_ms / 1000,
                                end=end_ms / 1000,
                            )
                        )
                finally:
                    # Cleanup chunk file
                    if chunk_path.exists():
                        os.remove(chunk_path)

                # Move to next chunk (with overlap consideration)
                start_ms = end_ms - CHUNK_OVERLAP_MS if end_ms < total_duration_ms else end_ms
                chunk_index += 1

            return all_segments
        except Exception as e:
            logger.error(f"Error in chunked transcription: {e}")
            return []

    def _build_raw_content(self, segments: list[WhisperSegment]) -> str:
        """Build raw content with timestamps.

        Args:
            segments: List of WhisperSegments

        Returns:
            Formatted string with timestamps
        """
        lines = []
        for seg in segments:
            timestamp = self._format_timestamp(seg.start)
            lines.append(f"[{timestamp}] {seg.text}")
        return "\n".join(lines)

    def _build_clean_content(self, segments: list[WhisperSegment]) -> str:
        """Build clean content without timestamps.

        Args:
            segments: List of WhisperSegments

        Returns:
            Plain text transcript
        """
        return " ".join(seg.text for seg in segments)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def estimate_cost(self, duration_seconds: int) -> float:
        """Estimate transcription cost.

        Args:
            duration_seconds: Video duration in seconds

        Returns:
            Estimated cost in USD
        """
        minutes = duration_seconds / 60
        return minutes * 0.006  # $0.006 per minute
