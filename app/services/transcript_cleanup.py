"""Transcript cleanup service using OpenAI GPT."""

import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of transcript cleanup."""

    original: str
    cleaned: str
    language_code: str
    changes_summary: str


class TranscriptCleanupService:
    """Service for cleaning and fixing transcripts using OpenAI GPT."""

    def __init__(self, api_key: str = None):
        """Initialize the cleanup service.

        Args:
            api_key: OpenAI API key. If not provided, uses settings.
        """
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required for transcript cleanup")
        self.client = OpenAI(api_key=self.api_key)

    def cleanup_transcript(
        self,
        transcript: str,
        language_code: str = "fa",
        preserve_timestamps: bool = True,
        video_title: str = "",
        video_description: str = "",
        video_tags: list[str] = None,
        channel_context: str = "",
    ) -> Optional[CleanupResult]:
        """
        Clean up and fix a transcript using GPT.

        Args:
            transcript: The raw transcript text (with or without timestamps)
            language_code: Language code of the transcript
            preserve_timestamps: Whether to keep timestamps in output
            video_title: Title of the video for context
            video_description: Description of the video for context
            video_tags: Tags associated with the video
            channel_context: General context about the channel/content type

        Returns:
            CleanupResult or None if cleanup failed
        """
        try:
            # Build the prompt based on language
            language_name = self._get_language_name(language_code)

            # Build context section
            context_parts = []
            if video_title:
                context_parts.append(f"Video Title: {video_title}")
            if video_description:
                # Truncate long descriptions
                desc = video_description[:500] + "..." if len(video_description) > 500 else video_description
                context_parts.append(f"Video Description: {desc}")
            if video_tags:
                context_parts.append(f"Tags: {', '.join(video_tags[:15])}")
            if channel_context:
                context_parts.append(f"Channel Context: {channel_context}")

            context_section = ""
            if context_parts:
                context_section = f"""
VIDEO CONTEXT (use this to understand domain-specific terminology):
{chr(10).join(context_parts)}

Based on this context, pay special attention to:
- Technical terms related to the video topic
- Names, brands, or proper nouns mentioned
- Domain-specific vocabulary that might be mistranscribed
"""

            system_prompt = f"""You are a professional transcript editor for {language_name} content.
Your task is to clean up and fix the transcript while preserving the original meaning AND STYLE.
{context_section}
CRITICAL RULES:
1. PRESERVE THE ORIGINAL TONE AND STYLE - if the speaker uses informal/colloquial language, KEEP IT INFORMAL. Do NOT formalize the language.
2. Keep English technical terms in ENGLISH ALPHABET (not transliterated to {language_name}). Examples:
   - Keep "code" as "code" not "کد"
   - Keep "clean code" as "clean code" not "کلین کد"
   - Keep "function", "class", "variable", "Git", "GitHub", "Python", etc. in English
3. Fix spelling errors in {language_name} words only
4. Add proper punctuation where clearly needed
5. Fix obvious speech-to-text errors based on context
6. {"Preserve all timestamps in [MM:SS] or [HH:MM:SS] format exactly as they appear" if preserve_timestamps else "Remove timestamps"}
7. Keep the same line structure (one segment per line)
8. Do NOT translate or change the language direction
9. Do NOT add new content or remove meaningful content
10. Do NOT change informal speech patterns to formal ones (e.g., keep "میخوام" don't change to "می‌خواهم")
11. Remove only obvious filler sounds like "اوم", "آه" but keep natural speech patterns

IMPORTANT: The speaker's personality and speaking style should be preserved. If they speak casually, the output should be casual.

Output ONLY the cleaned transcript, nothing else."""

            user_prompt = f"""Clean up this {language_name} transcript:

{transcript}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective for this task
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=16000,
            )

            cleaned = response.choices[0].message.content.strip()

            # Generate a brief summary of changes
            changes_summary = self._generate_changes_summary(transcript, cleaned)

            return CleanupResult(
                original=transcript,
                cleaned=cleaned,
                language_code=language_code,
                changes_summary=changes_summary,
            )

        except Exception as e:
            logger.error(f"Error cleaning transcript: {e}")
            return None

    def _get_language_name(self, code: str) -> str:
        """Get language name from code."""
        languages = {
            "fa": "Persian (Farsi)",
            "en": "English",
            "ar": "Arabic",
            "tr": "Turkish",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
        }
        return languages.get(code, code)

    def _generate_changes_summary(self, original: str, cleaned: str) -> str:
        """Generate a brief summary of changes made."""
        original_words = len(original.split())
        cleaned_words = len(cleaned.split())

        original_lines = len(original.strip().split('\n'))
        cleaned_lines = len(cleaned.strip().split('\n'))

        diff_words = cleaned_words - original_words
        diff_lines = cleaned_lines - original_lines

        summary_parts = []

        if diff_words > 0:
            summary_parts.append(f"+{diff_words} words")
        elif diff_words < 0:
            summary_parts.append(f"{diff_words} words")

        if diff_lines != 0:
            summary_parts.append(f"{diff_lines:+d} lines")

        if not summary_parts:
            return "Minor formatting changes"

        return ", ".join(summary_parts)

    def estimate_cost(self, transcript: str) -> float:
        """Estimate cleanup cost.

        Args:
            transcript: The transcript text

        Returns:
            Estimated cost in USD
        """
        # Rough token estimate (1 token ≈ 4 chars for English, less for Persian)
        chars = len(transcript)
        estimated_tokens = chars / 3  # Conservative for non-English

        # GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output
        # Assume output ≈ input size
        input_cost = (estimated_tokens / 1_000_000) * 0.15
        output_cost = (estimated_tokens / 1_000_000) * 0.60

        return round(input_cost + output_cost, 4)
