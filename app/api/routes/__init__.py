"""API routes module."""

from fastapi import APIRouter

from app.api.routes import sync, videos, export

api_router = APIRouter()

api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
