"""Content creation wizard service using RAG and GPT."""

import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Video
from app.services.rag import get_rag_service

logger = logging.getLogger(__name__)


@dataclass
class OverlapCheckResult:
    """Result of checking overlap with existing content."""

    has_overlap: bool
    overlap_score: float  # 0-1, how much overlap
    related_videos: list[dict]  # List of related videos with relevance
    unique_angles: list[str]  # Suggested unique angles
    summary: str


@dataclass
class VideoOutline:
    """Generated video outline."""

    title: str
    hook: str  # Opening hook
    sections: list[dict]  # List of sections with title and bullets
    call_to_action: str
    estimated_duration: str
    target_audience: str


@dataclass
class VideoScript:
    """Generated video script."""

    title: str
    full_script: str
    sections: list[dict]  # Script broken into sections
    word_count: int
    estimated_duration_minutes: int


class ContentWizardService:
    """Service for AI-powered content creation assistance."""

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.rag = get_rag_service()

    def check_overlap(
        self,
        topic: str,
        db: Session,
        top_k: int = 10,
    ) -> OverlapCheckResult:
        """
        Check if a topic overlaps with existing content.

        Args:
            topic: The proposed video topic or idea
            db: Database session
            top_k: Number of similar videos to check

        Returns:
            OverlapCheckResult with analysis
        """
        # Search for related content using RAG
        search_results = self.rag.search(topic, top_k=top_k)

        if not search_results:
            return OverlapCheckResult(
                has_overlap=False,
                overlap_score=0.0,
                related_videos=[],
                unique_angles=[
                    "This appears to be a new topic for your channel!",
                    "You have full creative freedom with this topic.",
                ],
                summary="No existing content found on this topic. This could be a great opportunity for new content!",
            )

        # Group by video and calculate relevance
        video_relevance: dict[str, dict] = {}
        for result in search_results:
            vid = result["video_id"]
            if vid not in video_relevance:
                video_relevance[vid] = {
                    "video_id": vid,
                    "title": result["video_title"],
                    "relevance_score": 0,
                    "matching_segments": [],
                }
            # Lower distance = higher relevance
            relevance = max(0, 1 - (result["score"] / 100))
            video_relevance[vid]["relevance_score"] = max(
                video_relevance[vid]["relevance_score"], relevance
            )
            video_relevance[vid]["matching_segments"].append(
                result["text"][:200] + "..."
            )

        related_videos = sorted(
            video_relevance.values(),
            key=lambda x: x["relevance_score"],
            reverse=True,
        )[:5]

        # Calculate overall overlap score
        if related_videos:
            avg_relevance = sum(v["relevance_score"] for v in related_videos) / len(
                related_videos
            )
            overlap_score = min(1.0, avg_relevance * 1.5)  # Scale up slightly
        else:
            overlap_score = 0.0

        has_overlap = overlap_score > 0.3

        # Generate unique angles using GPT
        unique_angles = self._generate_unique_angles(topic, related_videos)

        # Generate summary
        if has_overlap:
            summary = f"Found {len(related_videos)} related video(s). Overlap score: {overlap_score:.0%}. Consider the suggested unique angles to differentiate your content."
        else:
            summary = "Low overlap with existing content. You can approach this topic freely while potentially referencing related videos."

        return OverlapCheckResult(
            has_overlap=has_overlap,
            overlap_score=overlap_score,
            related_videos=related_videos,
            unique_angles=unique_angles,
            summary=summary,
        )

    def _generate_unique_angles(
        self, topic: str, related_videos: list[dict]
    ) -> list[str]:
        """Generate unique angles for a topic given existing content."""
        if not related_videos:
            return [
                "Fresh perspective - no prior content on this topic",
                "Introduce the concept from scratch",
                "Build a foundation for future content",
            ]

        existing_content = "\n".join(
            f"- {v['title']}" for v in related_videos[:5]
        )

        prompt = f"""Given this video topic idea: "{topic}"

And these existing videos on similar topics:
{existing_content}

Suggest 3-5 unique angles or approaches that would make the new video different and valuable. Focus on:
- Different perspectives not covered
- Deeper dives into specific aspects
- Practical applications not shown before
- Updated information or new developments
- Different audience segments

Return as a simple list, one angle per line. Be concise (1-2 sentences each). Write in the same language as the topic."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )

        angles = response.choices[0].message.content.strip().split("\n")
        return [a.strip().lstrip("•-123456789. ") for a in angles if a.strip()]

    def generate_outline(
        self,
        topic: str,
        angle: Optional[str] = None,
        target_duration: str = "10-15 minutes",
        include_rag_context: bool = True,
    ) -> VideoOutline:
        """
        Generate a video outline for a topic.

        Args:
            topic: The video topic
            angle: Specific angle or approach (optional)
            target_duration: Target video duration
            include_rag_context: Whether to include context from existing videos

        Returns:
            VideoOutline with structured outline
        """
        # Get context from existing videos if requested
        context = ""
        if include_rag_context:
            search_results = self.rag.search(topic, top_k=5)
            if search_results:
                context_parts = [
                    f"From '{r['video_title']}':\n{r['text'][:300]}..."
                    for r in search_results[:3]
                ]
                context = f"""
CONTEXT FROM YOUR EXISTING VIDEOS (reference or build upon these):
{chr(10).join(context_parts)}
"""

        angle_instruction = f"\nSPECIFIC ANGLE: {angle}" if angle else ""

        prompt = f"""Create a detailed video outline for a YouTube video.

TOPIC: {topic}{angle_instruction}
TARGET DURATION: {target_duration}
{context}

Create an outline in JSON format with:
{{
    "title": "Engaging video title",
    "hook": "Opening hook (first 30 seconds) to grab attention",
    "sections": [
        {{
            "title": "Section title",
            "duration": "estimated minutes",
            "bullets": ["key point 1", "key point 2", "key point 3"]
        }}
    ],
    "call_to_action": "What viewers should do after watching",
    "target_audience": "Who this video is for"
}}

Guidelines:
- Make the title catchy but clear
- Hook should create curiosity or address a pain point
- Include 3-6 main sections
- Each section should have 2-4 key points
- Write in the same language as the topic
- Match an informal, practical, educational tone

Return ONLY the JSON, no other text."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
        )

        import json

        try:
            content = response.choices[0].message.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            outline_data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback outline
            outline_data = {
                "title": topic,
                "hook": "Start with the problem this topic solves",
                "sections": [
                    {"title": "Introduction", "duration": "2 min", "bullets": ["Context", "Why this matters"]},
                    {"title": "Main Content", "duration": "8 min", "bullets": ["Key concept 1", "Key concept 2"]},
                    {"title": "Conclusion", "duration": "2 min", "bullets": ["Summary", "Next steps"]},
                ],
                "call_to_action": "Like, subscribe, and comment",
                "target_audience": "General audience interested in this topic",
            }

        return VideoOutline(
            title=outline_data.get("title", topic),
            hook=outline_data.get("hook", ""),
            sections=outline_data.get("sections", []),
            call_to_action=outline_data.get("call_to_action", ""),
            estimated_duration=target_duration,
            target_audience=outline_data.get("target_audience", ""),
        )

    def generate_script(
        self,
        outline: VideoOutline,
        style: str = "conversational",
        include_timestamps: bool = True,
    ) -> VideoScript:
        """
        Generate a full video script from an outline.

        Args:
            outline: The video outline to expand
            style: Writing style (conversational, formal, educational)
            include_timestamps: Whether to include timing markers

        Returns:
            VideoScript with full script
        """
        sections_text = "\n".join(
            f"Section: {s['title']}\nDuration: {s.get('duration', 'N/A')}\nPoints: {', '.join(s.get('bullets', []))}"
            for s in outline.sections
        )

        prompt = f"""Write a complete YouTube video script based on this outline.

TITLE: {outline.title}
HOOK: {outline.hook}
TARGET AUDIENCE: {outline.target_audience}

SECTIONS:
{sections_text}

CALL TO ACTION: {outline.call_to_action}

Guidelines:
- Style: {style} - speak directly to the viewer
- Use "you" and "we" to engage the audience
- Include natural transitions between sections
- Add examples and analogies where helpful
- {"Include [TIMESTAMP] markers at section breaks" if include_timestamps else "No timestamps needed"}
- Write the full spoken words (not just bullet points)
- Match the language of the outline
- Keep sentences short and punchy for video
- Add personality and occasional humor

Format the script with clear section headers and natural speaking flow."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4000,
        )

        full_script = response.choices[0].message.content.strip()

        # Count words and estimate duration
        word_count = len(full_script.split())
        # Average speaking rate: ~150 words per minute
        estimated_minutes = word_count // 150

        # Parse sections from script (simple approach)
        script_sections = []
        current_section = {"title": "Introduction", "content": ""}
        for line in full_script.split("\n"):
            if line.startswith("#") or line.startswith("**") and line.endswith("**"):
                if current_section["content"]:
                    script_sections.append(current_section)
                current_section = {
                    "title": line.strip("#* "),
                    "content": "",
                }
            else:
                current_section["content"] += line + "\n"
        if current_section["content"]:
            script_sections.append(current_section)

        return VideoScript(
            title=outline.title,
            full_script=full_script,
            sections=script_sections,
            word_count=word_count,
            estimated_duration_minutes=estimated_minutes,
        )

    def suggest_series_episodes(
        self,
        series_topic: str,
        db: Session,
        num_suggestions: int = 5,
    ) -> dict:
        """
        Suggest new episodes for a video series.

        Args:
            series_topic: The series topic/theme
            db: Database session
            num_suggestions: Number of episode suggestions

        Returns:
            Dict with existing episodes and suggestions
        """
        # Find existing videos on this topic
        search_results = self.rag.search(series_topic, top_k=20)

        # Group by video to get unique videos
        existing_videos = {}
        for result in search_results:
            vid = result["video_id"]
            if vid not in existing_videos:
                existing_videos[vid] = {
                    "video_id": vid,
                    "title": result["video_title"],
                }

        existing_list = list(existing_videos.values())[:10]
        existing_titles = "\n".join(f"- {v['title']}" for v in existing_list)

        prompt = f"""You are a YouTube content strategist for a channel about programming, career development, and LinkedIn optimization.

SERIES TOPIC: {series_topic}

EXISTING EPISODES IN THIS SERIES:
{existing_titles if existing_titles else "No existing episodes found."}

Suggest {num_suggestions} new episode ideas that:
1. Don't repeat existing content
2. Logically extend the series
3. Address viewer questions or gaps
4. Build on previous episodes

Format as JSON:
{{
    "series_summary": "Brief description of the series theme",
    "existing_coverage": "What topics are already covered",
    "gaps_identified": ["gap 1", "gap 2"],
    "suggestions": [
        {{
            "title": "Episode title",
            "description": "2-3 sentence description",
            "builds_on": "Which existing episode this relates to (if any)",
            "unique_value": "What makes this episode valuable"
        }}
    ]
}}

Write in the same language as the series topic. Return ONLY JSON."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=2000,
        )

        import json

        try:
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            suggestions = json.loads(content)
        except json.JSONDecodeError:
            suggestions = {
                "series_summary": series_topic,
                "existing_coverage": "Unable to parse",
                "gaps_identified": [],
                "suggestions": [],
            }

        return {
            "series_topic": series_topic,
            "existing_episodes": existing_list,
            **suggestions,
        }

    def find_clip_candidates(
        self,
        video_id: str,
        db: Session,
        num_clips: int = 5,
    ) -> list[dict]:
        """
        Find potential clip/shorts candidates from a video transcript.

        Args:
            video_id: The video ID to analyze
            db: Database session
            num_clips: Number of clip suggestions

        Returns:
            List of clip candidates with timestamps and hooks
        """
        # Get the video and its transcript
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.transcripts:
            return []

        # Get the best transcript
        transcript = None
        for source in ["cleaned", "whisper", "youtube"]:
            for t in video.transcripts:
                if t.source == source:
                    transcript = t
                    break
            if transcript:
                break

        if not transcript:
            transcript = video.transcripts[0]

        # Use raw content if it has timestamps
        content = transcript.raw_content if transcript.raw_content else transcript.clean_content

        prompt = f"""Analyze this video transcript and find {num_clips} segments that would make great short-form clips (30-60 seconds each).

VIDEO TITLE: {video.title}

TRANSCRIPT:
{content[:8000]}  # Limit to avoid token limits

For each clip candidate, identify:
1. The exact timestamp range (if visible in transcript)
2. A catchy hook sentence to start the clip
3. Why this segment would work well as a standalone clip

Look for:
- Strong opinions or hot takes
- Practical tips or actionable advice
- Emotional moments or stories
- Surprising facts or insights
- Clear explanations of complex topics

Format as JSON:
{{
    "clips": [
        {{
            "start_time": "MM:SS or estimated position",
            "end_time": "MM:SS or estimated position",
            "hook": "Attention-grabbing first line",
            "content_summary": "What this clip is about",
            "why_it_works": "Why this would perform well",
            "suggested_title": "Title for the short"
        }}
    ]
}}

Return ONLY JSON."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )

        import json

        try:
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content)
            clips = result.get("clips", [])
        except json.JSONDecodeError:
            clips = []

        # Add video info to each clip
        for clip in clips:
            clip["video_id"] = video_id
            clip["video_title"] = video.title

        return clips


# Singleton instance
_wizard_service: ContentWizardService | None = None


def get_wizard_service() -> ContentWizardService:
    """Get or create wizard service singleton."""
    global _wizard_service
    if _wizard_service is None:
        _wizard_service = ContentWizardService()
    return _wizard_service
