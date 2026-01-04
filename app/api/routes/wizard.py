"""Content creation wizard API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.content_wizard import get_wizard_service

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response Models


class OverlapCheckRequest(BaseModel):
    """Request for checking content overlap."""

    topic: str
    top_k: int = 10


class RelatedVideo(BaseModel):
    """Related video in overlap check."""

    video_id: str
    title: str
    relevance_score: float
    matching_segments: list[str]


class OverlapCheckResponse(BaseModel):
    """Response for overlap check."""

    has_overlap: bool
    overlap_score: float
    related_videos: list[RelatedVideo]
    unique_angles: list[str]
    summary: str


class OutlineRequest(BaseModel):
    """Request for generating outline."""

    topic: str
    angle: Optional[str] = None
    target_duration: str = "10-15 minutes"
    include_rag_context: bool = True


class OutlineSection(BaseModel):
    """Section in video outline."""

    title: str
    duration: Optional[str] = None
    bullets: list[str] = []


class OutlineResponse(BaseModel):
    """Response for outline generation."""

    title: str
    hook: str
    sections: list[OutlineSection]
    call_to_action: str
    estimated_duration: str
    target_audience: str


class ScriptRequest(BaseModel):
    """Request for generating script."""

    title: str
    hook: str
    sections: list[OutlineSection]
    call_to_action: str
    target_audience: str
    style: str = "conversational"
    include_timestamps: bool = True


class ScriptSection(BaseModel):
    """Section in video script."""

    title: str
    content: str


class ScriptResponse(BaseModel):
    """Response for script generation."""

    title: str
    full_script: str
    sections: list[ScriptSection]
    word_count: int
    estimated_duration_minutes: int


class SeriesSuggestionRequest(BaseModel):
    """Request for series episode suggestions."""

    series_topic: str
    num_suggestions: int = 5


class EpisodeSuggestion(BaseModel):
    """Suggested episode."""

    title: str
    description: str
    builds_on: Optional[str] = None
    unique_value: str


class SeriesSuggestionResponse(BaseModel):
    """Response for series suggestions."""

    series_topic: str
    existing_episodes: list[dict]
    series_summary: str
    existing_coverage: str
    gaps_identified: list[str]
    suggestions: list[EpisodeSuggestion]


class ClipCandidate(BaseModel):
    """Clip candidate from video."""

    video_id: str
    video_title: str
    start_time: str
    end_time: str
    hook: str
    content_summary: str
    why_it_works: str
    suggested_title: str


class ClipCandidatesResponse(BaseModel):
    """Response for clip candidates."""

    video_id: str
    clips: list[ClipCandidate]


# Endpoints


@router.post("/overlap-check", response_model=OverlapCheckResponse)
def check_content_overlap(
    request: OverlapCheckRequest,
    db: Session = Depends(get_db),
):
    """
    Check if a topic overlaps with existing channel content.

    Uses RAG to find related videos and suggests unique angles.
    """
    wizard = get_wizard_service()
    result = wizard.check_overlap(
        topic=request.topic,
        db=db,
        top_k=request.top_k,
    )

    return OverlapCheckResponse(
        has_overlap=result.has_overlap,
        overlap_score=result.overlap_score,
        related_videos=[
            RelatedVideo(
                video_id=v["video_id"],
                title=v["title"],
                relevance_score=v["relevance_score"],
                matching_segments=v.get("matching_segments", [])[:2],
            )
            for v in result.related_videos
        ],
        unique_angles=result.unique_angles,
        summary=result.summary,
    )


@router.post("/generate-outline", response_model=OutlineResponse)
def generate_video_outline(request: OutlineRequest):
    """
    Generate a video outline for a topic.

    Can include context from existing videos via RAG.
    """
    wizard = get_wizard_service()
    outline = wizard.generate_outline(
        topic=request.topic,
        angle=request.angle,
        target_duration=request.target_duration,
        include_rag_context=request.include_rag_context,
    )

    return OutlineResponse(
        title=outline.title,
        hook=outline.hook,
        sections=[
            OutlineSection(
                title=s.get("title", ""),
                duration=s.get("duration"),
                bullets=s.get("bullets", []),
            )
            for s in outline.sections
        ],
        call_to_action=outline.call_to_action,
        estimated_duration=outline.estimated_duration,
        target_audience=outline.target_audience,
    )


@router.post("/generate-script", response_model=ScriptResponse)
def generate_video_script(request: ScriptRequest):
    """
    Generate a full video script from an outline.
    """
    from app.services.content_wizard import VideoOutline

    wizard = get_wizard_service()

    # Convert request to VideoOutline
    outline = VideoOutline(
        title=request.title,
        hook=request.hook,
        sections=[
            {"title": s.title, "duration": s.duration, "bullets": s.bullets}
            for s in request.sections
        ],
        call_to_action=request.call_to_action,
        estimated_duration="",
        target_audience=request.target_audience,
    )

    script = wizard.generate_script(
        outline=outline,
        style=request.style,
        include_timestamps=request.include_timestamps,
    )

    return ScriptResponse(
        title=script.title,
        full_script=script.full_script,
        sections=[
            ScriptSection(title=s["title"], content=s["content"])
            for s in script.sections
        ],
        word_count=script.word_count,
        estimated_duration_minutes=script.estimated_duration_minutes,
    )


@router.post("/series-suggestions", response_model=SeriesSuggestionResponse)
def get_series_suggestions(
    request: SeriesSuggestionRequest,
    db: Session = Depends(get_db),
):
    """
    Get episode suggestions for a video series.

    Analyzes existing content and suggests new episodes.
    """
    wizard = get_wizard_service()
    result = wizard.suggest_series_episodes(
        series_topic=request.series_topic,
        db=db,
        num_suggestions=request.num_suggestions,
    )

    return SeriesSuggestionResponse(
        series_topic=result["series_topic"],
        existing_episodes=result.get("existing_episodes", []),
        series_summary=result.get("series_summary", ""),
        existing_coverage=result.get("existing_coverage", ""),
        gaps_identified=result.get("gaps_identified", []),
        suggestions=[
            EpisodeSuggestion(
                title=s.get("title", ""),
                description=s.get("description", ""),
                builds_on=s.get("builds_on"),
                unique_value=s.get("unique_value", ""),
            )
            for s in result.get("suggestions", [])
        ],
    )


@router.get("/clip-candidates/{video_id}", response_model=ClipCandidatesResponse)
def find_clip_candidates(
    video_id: str,
    num_clips: int = 5,
    db: Session = Depends(get_db),
):
    """
    Find potential short-form clip candidates from a video.

    Analyzes the transcript to find engaging segments.
    """
    wizard = get_wizard_service()
    clips = wizard.find_clip_candidates(
        video_id=video_id,
        db=db,
        num_clips=num_clips,
    )

    if not clips:
        raise HTTPException(
            status_code=404,
            detail="No clips found. Make sure the video has a transcript.",
        )

    return ClipCandidatesResponse(
        video_id=video_id,
        clips=[
            ClipCandidate(
                video_id=c.get("video_id", video_id),
                video_title=c.get("video_title", ""),
                start_time=c.get("start_time", ""),
                end_time=c.get("end_time", ""),
                hook=c.get("hook", ""),
                content_summary=c.get("content_summary", ""),
                why_it_works=c.get("why_it_works", ""),
                suggested_title=c.get("suggested_title", ""),
            )
            for c in clips
        ],
    )


@router.post("/quick-idea")
def generate_quick_idea(
    topic: str,
    db: Session = Depends(get_db),
):
    """
    Quick endpoint: Check overlap + generate outline in one call.
    """
    wizard = get_wizard_service()

    # Check overlap
    overlap = wizard.check_overlap(topic=topic, db=db, top_k=5)

    # Pick the best angle
    best_angle = overlap.unique_angles[0] if overlap.unique_angles else None

    # Generate outline with that angle
    outline = wizard.generate_outline(
        topic=topic,
        angle=best_angle,
        target_duration="10-15 minutes",
        include_rag_context=True,
    )

    return {
        "topic": topic,
        "overlap_check": {
            "has_overlap": overlap.has_overlap,
            "overlap_score": overlap.overlap_score,
            "summary": overlap.summary,
            "related_videos": [
                {"video_id": v["video_id"], "title": v["title"]}
                for v in overlap.related_videos[:3]
            ],
        },
        "suggested_angle": best_angle,
        "outline": {
            "title": outline.title,
            "hook": outline.hook,
            "sections": outline.sections,
            "call_to_action": outline.call_to_action,
            "target_audience": outline.target_audience,
        },
    }
