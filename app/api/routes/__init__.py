"""API routes module."""

from fastapi import APIRouter

from app.api.routes import sync, videos, export, whisper, transcripts, dubbing, batch, rag

api_router = APIRouter()

api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(whisper.router, prefix="/whisper", tags=["whisper"])
api_router.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
api_router.include_router(dubbing.router, prefix="/dubbing", tags=["dubbing"])
api_router.include_router(batch.router, prefix="/batch", tags=["batch"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
