"""Transcript cleanup service using OpenAI GPT."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

# Path to cleanup config file
CLEANUP_CONFIG_PATH = Path("data/cleanup_config.json")


def load_cleanup_config() -> dict:
    """Load cleanup configuration from JSON file."""
    if CLEANUP_CONFIG_PATH.exists():
        try:
            with open(CLEANUP_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cleanup config: {e}")
    return {}


def save_cleanup_config(config: dict) -> bool:
    """Save cleanup configuration to JSON file."""
    try:
        CLEANUP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CLEANUP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save cleanup config: {e}")
        return False


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
        self.config = load_cleanup_config()

    def reload_config(self):
        """Reload configuration from file."""
        self.config = load_cleanup_config()

    def _preprocess_text(self, text: str, language_code: str) -> str:
        """
        Pre-process text to fix common transcription errors using config.

        Args:
            text: Raw transcript text
            language_code: Language code

        Returns:
            Pre-processed text with term corrections applied
        """
        result = text

        # Apply term corrections from config
        term_corrections = self.config.get("term_corrections", {})
        for wrong, correct in term_corrections.items():
            result = result.replace(wrong, correct)

        # Apply speaker name correction if configured
        speaker = self.config.get("speaker", {})
        if speaker.get("name") and speaker.get("introduction_pattern"):
            for variation in speaker.get("name_variations", []):
                if variation != speaker["name"]:
                    # Fix speaker introduction pattern
                    pattern = rf"{variation}\s+هم\s+برنامه"
                    replacement = f"{speaker['introduction_pattern']} برنامه"
                    result = re.sub(pattern, replacement, result)

        # Common half-space fixes for Persian
        if language_code == "fa":
            result = re.sub(r"برنامه\s+نویس", "برنامه‌نویس", result)
            result = re.sub(r"می\s+([گخشکب])", r"می‌\1", result)  # می + verb
            result = re.sub(r"نمی\s+([گخشکب])", r"نمی‌\1", result)  # نمی + verb

        return result

    def _build_few_shot_prompt(self) -> str:
        """Build few-shot examples section from config."""
        examples = self.config.get("few_shot_examples", [])
        if not examples:
            return ""

        parts = ["\n\nEXAMPLES OF CORRECT CLEANUP (follow this style exactly):"]
        for i, ex in enumerate(examples[:5], 1):  # Max 5 examples
            parts.append(f"\nExample {i}:")
            parts.append(f"Input: {ex.get('input', '')}")
            parts.append(f"Output: {ex.get('output', '')}")

        return "\n".join(parts)

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
            # Pre-process to fix common errors using config
            transcript = self._preprocess_text(transcript, language_code)

            # Build the prompt based on language
            language_name = self._get_language_name(language_code)

            # Build context section from config and parameters
            context_parts = []

            # Add channel context from config
            channel_config = self.config.get("channel", {})
            if channel_config.get("context"):
                context_parts.append(f"Channel: {channel_config['context']}")
            if channel_config.get("style"):
                context_parts.append(f"Speaking Style: {channel_config['style']}")

            # Add speaker info from config
            speaker_config = self.config.get("speaker", {})
            if speaker_config.get("name"):
                context_parts.append(f"Speaker Name: {speaker_config['name']}")

            # Add video-specific context
            if video_title:
                context_parts.append(f"Video Title: {video_title}")
            if video_description:
                desc = video_description[:500] + "..." if len(video_description) > 500 else video_description
                context_parts.append(f"Video Description: {desc}")
            if video_tags:
                context_parts.append(f"Tags: {', '.join(video_tags[:15])}")
            if channel_context:
                context_parts.append(f"Additional Context: {channel_context}")

            context_section = ""
            if context_parts:
                context_section = f"""
VIDEO CONTEXT:
{chr(10).join(context_parts)}
"""

            # Build style rules from config
            style_rules = self.config.get("style_rules", [])
            style_rules_section = ""
            if style_rules:
                style_rules_section = "\nSTYLE RULES (MUST FOLLOW):\n" + "\n".join(f"- {rule}" for rule in style_rules)

            # Build few-shot examples section
            few_shot_section = self._build_few_shot_prompt()

            # Persian-specific instructions (as fallback if no config)
            persian_rules = ""
            if language_code == "fa" and not style_rules:
                persian_rules = """
PERSIAN-SPECIFIC RULES:
- Keep colloquial endings: "پروفایلمون" NOT "پروفایل ما", "کارامون" NOT "کارهای ما"
- Keep informal verb forms: "بکنیم", "بکنن", "می‌خوره" - do NOT formalize
- Keep spoken contractions: "قراره" not "قرار است", "میشه" not "می‌شود"
- Use half-space (نیم‌فاصله) for compound words: "برنامه‌نویس", "می‌گردن"
- Preserve original word order even if grammatically informal
- Do NOT change "یه" to "یک" - keep the spoken form
"""

            system_prompt = f"""You are a professional transcript editor for {language_name} content.
Your task is to clean up and fix the transcript while preserving the original meaning AND STYLE.
{context_section}
CRITICAL RULES:
1. PRESERVE THE ORIGINAL TONE AND STYLE - if the speaker uses informal/colloquial language, KEEP IT INFORMAL. Do NOT formalize the language.
2. Keep English technical terms in ENGLISH ALPHABET (not transliterated to {language_name}).
3. Fix spelling errors in {language_name} words only
4. Add proper punctuation where clearly needed
5. Fix obvious speech-to-text errors based on context
6. {"Preserve all timestamps in [MM:SS] or [HH:MM:SS] format exactly as they appear" if preserve_timestamps else "Remove timestamps"}
7. Keep the same line structure (one segment per line)
8. Do NOT translate or change the language direction
9. Do NOT add new content or remove meaningful content
10. Do NOT change informal speech patterns to formal ones
11. Remove only obvious filler sounds like "اوم", "آه" but keep natural speech patterns
{style_rules_section}
{persian_rules}
{few_shot_section}

IMPORTANT: Follow the examples above exactly. The speaker's personality and speaking style MUST be preserved.

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
