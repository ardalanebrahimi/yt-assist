"""Dubbing service - translate transcripts and generate TTS audio."""

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from openai import OpenAI
from pydub import AudioSegment

from app.config import get_settings

logger = logging.getLogger(__name__)


def _find_ffmpeg() -> str | None:
    """Find FFmpeg installation path."""
    import shutil

    # Check if ffmpeg is in PATH
    if shutil.which("ffmpeg"):
        return None  # Use system PATH

    # Common Windows installation paths
    common_paths = [
        Path("C:/Program Files/Shotcut"),
        Path("C:/Program Files/ffmpeg/bin"),
        Path("C:/ffmpeg/bin"),
        Path("C:/tools/ffmpeg/bin"),
        Path.home() / "AppData/Local/Microsoft/WinGet/Links",
    ]

    for path in common_paths:
        ffmpeg_exe = path / "ffmpeg.exe"
        if ffmpeg_exe.exists():
            return str(path)

    return None


# Configure pydub to find FFmpeg
_ffmpeg_path = _find_ffmpeg()
if _ffmpeg_path:
    AudioSegment.converter = str(Path(_ffmpeg_path) / "ffmpeg.exe")
    AudioSegment.ffprobe = str(Path(_ffmpeg_path) / "ffprobe.exe")


@dataclass
class TranscriptSegment:
    """A segment of transcript with timing."""

    start_seconds: float
    end_seconds: float
    text: str
    translated_text: Optional[str] = None


@dataclass
class DubbingResult:
    """Result of dubbing operation."""

    audio_path: str
    duration_seconds: float
    segments_count: int
    source_language: str
    target_language: str


class DubbingService:
    """Service for creating dubbed audio from transcripts."""

    # OpenAI TTS voices
    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    # TTS models
    MODELS = {
        "standard": "tts-1",      # Faster, lower quality
        "hd": "tts-1-hd",         # Slower, higher quality
    }

    def __init__(self, api_key: str = None):
        """Initialize the dubbing service.

        Args:
            api_key: OpenAI API key. If not provided, uses settings.
        """
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required for dubbing")
        self.client = OpenAI(api_key=self.api_key)
        self.output_dir = Path("data/dubs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_transcript_segments(self, transcript: str) -> list[TranscriptSegment]:
        """Parse transcript with timestamps into segments.

        Supports formats:
        - [MM:SS] text
        - [HH:MM:SS] text

        Args:
            transcript: Raw transcript with timestamps

        Returns:
            List of TranscriptSegment objects
        """
        segments = []
        lines = transcript.strip().split("\n")

        # Pattern for timestamps: [MM:SS] or [HH:MM:SS]
        timestamp_pattern = r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]"

        for i, line in enumerate(lines):
            match = re.match(timestamp_pattern, line.strip())
            if match:
                # Parse timestamp
                groups = match.groups()
                if groups[2]:  # HH:MM:SS format
                    hours, minutes, seconds = int(groups[0]), int(groups[1]), int(groups[2])
                else:  # MM:SS format
                    hours, minutes, seconds = 0, int(groups[0]), int(groups[1])

                start_seconds = hours * 3600 + minutes * 60 + seconds

                # Extract text after timestamp
                text = re.sub(timestamp_pattern, "", line).strip()

                if text:
                    segments.append(TranscriptSegment(
                        start_seconds=start_seconds,
                        end_seconds=0,  # Will be calculated
                        text=text,
                    ))

        # Calculate end times based on next segment's start
        for i in range(len(segments) - 1):
            segments[i].end_seconds = segments[i + 1].start_seconds

        # Last segment: estimate based on text length (avg 150 words/min)
        if segments:
            last = segments[-1]
            word_count = len(last.text.split())
            estimated_duration = max(2, word_count / 2.5)  # ~150 wpm
            last.end_seconds = last.start_seconds + estimated_duration

        return segments

    def translate_segments(
        self,
        segments: list[TranscriptSegment],
        source_language: str,
        target_language: str,
        video_context: str = "",
    ) -> list[TranscriptSegment]:
        """Translate transcript segments to target language.

        Args:
            segments: List of transcript segments
            source_language: Source language code (e.g., 'fa')
            target_language: Target language code (e.g., 'en')
            video_context: Optional context about the video content

        Returns:
            Segments with translated_text filled in
        """
        if not segments:
            return segments

        lang_names = {
            "fa": "Persian (Farsi)",
            "en": "English",
            "ar": "Arabic",
            "tr": "Turkish",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
        }

        source_name = lang_names.get(source_language, source_language)
        target_name = lang_names.get(target_language, target_language)

        context_section = ""
        if video_context:
            context_section = f"\nVideo context: {video_context}\n"

        system_prompt = f"""You are a professional translator specializing in {source_name} to {target_name} translation.
{context_section}
RULES:
1. Translate naturally, not word-for-word
2. Preserve technical terms that are commonly used in English (like "code", "API", etc.)
3. Keep the same tone and style as the original
4. Each line is numbered - keep the same numbering in your output
5. Output ONLY the translations, one per line, with the same numbering
6. You MUST translate ALL lines provided - do not skip any

Example input:
1. سلام به همه
2. امروز میخوایم در مورد کد تمیز صحبت کنیم

Example output:
1. Hello everyone
2. Today we're going to talk about clean code"""

        # Process in batches of 50 segments to avoid truncation
        BATCH_SIZE = 50
        all_translations = {}

        for batch_start in range(0, len(segments), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(segments))
            batch_segments = segments[batch_start:batch_end]

            # Create numbered text for this batch (use global indices)
            numbered_text = "\n".join(
                f"{batch_start + i + 1}. {s.text}"
                for i, s in enumerate(batch_segments)
            )

            user_prompt = f"Translate these {source_name} lines to {target_name}:\n\n{numbered_text}"

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                )

                translated = response.choices[0].message.content.strip()

                # Parse numbered translations
                for line in translated.split("\n"):
                    match = re.match(r"(\d+)\.\s*(.+)", line.strip())
                    if match:
                        idx = int(match.group(1)) - 1  # Convert to 0-based
                        text = match.group(2).strip()
                        all_translations[idx] = text

                logger.info(f"Translated batch {batch_start}-{batch_end} ({len(batch_segments)} segments)")

            except Exception as e:
                logger.error(f"Translation error for batch {batch_start}-{batch_end}: {e}")

        # Apply all translations to segments
        missing_count = 0
        for i, segment in enumerate(segments):
            if i in all_translations:
                segment.translated_text = all_translations[i]
            else:
                # Fallback: keep original
                segment.translated_text = segment.text
                missing_count += 1

        if missing_count > 0:
            logger.warning(f"Missing translations for {missing_count} segments")

        return segments

    def generate_segment_audio(
        self,
        text: str,
        voice: str = "nova",
        model: str = "tts-1",
    ) -> bytes:
        """Generate TTS audio for a single segment.

        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            model: TTS model (tts-1 or tts-1-hd)

        Returns:
            Audio data as bytes (MP3 format)
        """
        response = self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
        )

        return response.content

    def create_dubbed_audio(
        self,
        segments: list[TranscriptSegment],
        voice: str = "nova",
        model: str = "tts-1",
        output_filename: str = None,
    ) -> str:
        """Create full dubbed audio from translated segments.

        Args:
            segments: Translated transcript segments
            voice: TTS voice to use
            model: TTS model to use
            output_filename: Output filename (without extension)

        Returns:
            Path to the output audio file
        """
        if not segments:
            raise ValueError("No segments to dub")

        # Create output audio
        final_audio = AudioSegment.silent(duration=0)
        current_position = 0

        for i, segment in enumerate(segments):
            text = segment.translated_text or segment.text
            target_start_ms = int(segment.start_seconds * 1000)

            # Add silence to reach the target start time
            if target_start_ms > current_position:
                silence_duration = target_start_ms - current_position
                final_audio += AudioSegment.silent(duration=silence_duration)
                current_position = target_start_ms

            # Generate audio for this segment
            try:
                audio_bytes = self.generate_segment_audio(text, voice, model)

                # Load audio from bytes
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                segment_audio = AudioSegment.from_mp3(tmp_path)
                Path(tmp_path).unlink()  # Clean up temp file

                # Add segment audio
                final_audio += segment_audio
                current_position += len(segment_audio)

                logger.info(f"Generated audio for segment {i+1}/{len(segments)}")

            except Exception as e:
                logger.error(f"Error generating audio for segment {i}: {e}")
                # Add silence for failed segment
                estimated_duration = max(1000, len(text.split()) * 400)  # ~150 wpm
                final_audio += AudioSegment.silent(duration=estimated_duration)
                current_position += estimated_duration

        # Export final audio
        if not output_filename:
            output_filename = f"dub_{len(segments)}segs"

        output_path = self.output_dir / f"{output_filename}.mp3"
        final_audio.export(str(output_path), format="mp3")

        return str(output_path)

    def dub_transcript(
        self,
        transcript: str,
        source_language: str = "fa",
        target_language: str = "en",
        voice: str = "nova",
        model: str = "tts-1",
        video_id: str = None,
        video_context: str = "",
    ) -> Optional[DubbingResult]:
        """Full dubbing pipeline: parse, translate, generate audio.

        Args:
            transcript: Raw transcript with timestamps
            source_language: Source language code
            target_language: Target language code
            voice: TTS voice to use
            model: TTS model to use
            video_id: Optional video ID for output filename
            video_context: Optional context about the video

        Returns:
            DubbingResult or None if failed
        """
        try:
            # Step 1: Parse transcript into segments
            logger.info("Parsing transcript segments...")
            segments = self.parse_transcript_segments(transcript)

            if not segments:
                logger.error("No segments found in transcript")
                return None

            logger.info(f"Found {len(segments)} segments")

            # Step 2: Translate segments
            logger.info(f"Translating from {source_language} to {target_language}...")
            segments = self.translate_segments(
                segments,
                source_language,
                target_language,
                video_context,
            )

            # Step 3: Generate dubbed audio
            logger.info(f"Generating audio with voice '{voice}'...")
            output_filename = f"{video_id}_{target_language}" if video_id else None
            audio_path = self.create_dubbed_audio(
                segments,
                voice=voice,
                model=model,
                output_filename=output_filename,
            )

            # Calculate total duration
            audio = AudioSegment.from_mp3(audio_path)
            duration_seconds = len(audio) / 1000

            return DubbingResult(
                audio_path=audio_path,
                duration_seconds=duration_seconds,
                segments_count=len(segments),
                source_language=source_language,
                target_language=target_language,
            )

        except Exception as e:
            logger.error(f"Dubbing failed: {e}")
            return None

    def estimate_cost(
        self,
        transcript: str,
        target_language: str = "en",
    ) -> dict:
        """Estimate dubbing cost.

        Args:
            transcript: Raw transcript
            target_language: Target language for translation

        Returns:
            Cost breakdown dict
        """
        segments = self.parse_transcript_segments(transcript)
        total_chars = sum(len(s.text) for s in segments)

        # Estimate translated length (English is usually shorter than Persian)
        lang_ratios = {"en": 0.7, "de": 0.9, "fr": 0.85, "es": 0.8}
        ratio = lang_ratios.get(target_language, 0.8)
        estimated_translated_chars = int(total_chars * ratio)

        # GPT-4o-mini translation cost: ~$0.15/1M input + $0.60/1M output
        translation_tokens = total_chars / 3  # Rough estimate
        translation_cost = (translation_tokens / 1_000_000) * 0.75

        # TTS cost: $0.015 per 1K characters
        tts_cost = (estimated_translated_chars / 1000) * 0.015

        return {
            "segments": len(segments),
            "source_characters": total_chars,
            "estimated_translated_characters": estimated_translated_chars,
            "translation_cost_usd": round(translation_cost, 4),
            "tts_cost_usd": round(tts_cost, 4),
            "total_cost_usd": round(translation_cost + tts_cost, 4),
        }
