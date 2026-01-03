"""RAG (Retrieval-Augmented Generation) API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Video, Transcript
from app.services.rag import get_rag_service

router = APIRouter()


class AskRequest(BaseModel):
    """Request model for asking questions."""

    question: str
    top_k: int = 5


class AskResponse(BaseModel):
    """Response model for answers."""

    answer: str
    sources: list[dict]
    chunks_used: int


class SearchRequest(BaseModel):
    """Request model for semantic search."""

    query: str
    top_k: int = 10


class SearchResult(BaseModel):
    """Search result model."""

    text: str
    video_id: str
    video_title: str
    score: float
    rank: int


class IndexStats(BaseModel):
    """Index statistics model."""

    total_chunks: int
    videos_indexed: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int


class IndexResult(BaseModel):
    """Result of indexing operation."""

    videos_processed: int
    total_chunks: int
    errors: list[dict]


class VideoIndexResult(BaseModel):
    """Result of indexing a single video."""

    video_id: str
    chunks_indexed: int
    message: str


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Ask a question about video content using RAG.

    The system will:
    1. Search for relevant transcript chunks
    2. Use GPT to generate an answer based on the context
    3. Return the answer with source citations
    """
    rag = get_rag_service()

    try:
        result = rag.ask(
            question=request.question,
            top_k=request.top_k,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=list[SearchResult])
async def semantic_search(request: SearchRequest):
    """
    Perform semantic search across indexed transcripts.

    Returns relevant chunks ranked by similarity.
    """
    rag = get_rag_service()

    try:
        results = rag.search(
            query=request.query,
            top_k=request.top_k,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=IndexStats)
async def get_index_stats():
    """Get statistics about the current RAG index."""
    rag = get_rag_service()
    return rag.get_index_stats()


@router.post("/index/all", response_model=IndexResult)
async def index_all_videos(db: Session = Depends(get_db)):
    """
    Index all videos with transcripts.

    This will rebuild the entire index from scratch.
    Useful for initial setup or full re-indexing.
    """
    rag = get_rag_service()

    try:
        result = rag.index_all_videos(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/{video_id}", response_model=VideoIndexResult)
async def index_video(video_id: str, db: Session = Depends(get_db)):
    """
    Index a single video's transcript.

    This will update (or add) the video in the index.
    """
    rag = get_rag_service()

    # Get video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get transcript
    transcript = None
    for source in ["cleaned", "whisper", "youtube"]:
        for t in video.transcripts:
            if t.source == source:
                transcript = t
                break
        if transcript:
            break

    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript found for this video")

    try:
        result = rag.index_video(video, transcript)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/indexed")
async def get_indexed_videos():
    """Get list of videos that are currently indexed."""
    rag = get_rag_service()
    stats = rag.get_index_stats()

    # Get unique video IDs from metadata
    video_ids = set()
    video_info = {}
    for chunk in rag.chunks_metadata:
        vid = chunk["video_id"]
        if vid not in video_ids:
            video_ids.add(vid)
            video_info[vid] = {
                "video_id": vid,
                "title": chunk["video_title"],
                "chunks": 0,
            }
        video_info[vid]["chunks"] += 1

    return {
        "total_videos": len(video_ids),
        "videos": list(video_info.values()),
    }


@router.delete("/index")
async def clear_index():
    """Clear the entire RAG index."""
    rag = get_rag_service()

    import faiss
    rag.index = faiss.IndexFlatL2(1536)  # EMBEDDING_DIMENSION
    rag.chunks_metadata = []
    rag._save_index()

    return {"message": "Index cleared successfully"}
