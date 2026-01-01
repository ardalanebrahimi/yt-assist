# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YT-Assist is a personal YouTube AI assistant for managing channel content, syncing video metadata and transcripts, and (in future phases) providing RAG-based Q&A and script generation in the channel owner's style.

**Current Phase:** Milestone 1 - Subtitle Ingestion MVP

## Commands

### Development Setup
```bash
# Backend (Python)
python -m venv venv
./venv/Scripts/pip install -r requirements.txt  # Windows
# or: venv/bin/pip install -r requirements.txt  # Unix

# Frontend (React)
cd web && npm install
```

### Running the Application
```bash
# Start FastAPI backend (port 8000)
./venv/Scripts/uvicorn app.main:app --reload

# Start React UI (port 5173) - in separate terminal
cd web && npm run dev
```

### Linting
```bash
./venv/Scripts/ruff check app/
./venv/Scripts/black --check app/
cd web && npx tsc --noEmit  # TypeScript check
```

## Architecture

```
UI (React + shadcn/ui) → FastAPI Backend → Services → SQLite DB
         ↓                                    ↓
      web/src/                          app/services/
      - pages/Library.tsx               - youtube.py (YouTube Data API)
      - lib/api.ts                      - transcripts.py (subtitle fetching)
      - components/ui/                  - sync.py (orchestration)
```

### Key Layers

- **`app/api/routes/`** - FastAPI endpoints: `/api/videos`, `/api/sync`, `/api/export`
- **`app/services/`** - Business logic: YouTubeService, TranscriptService, SyncService
- **`app/db/models.py`** - SQLAlchemy models: Video, Transcript
- **`web/src/pages/Library.tsx`** - Main React page for video management
- **`web/src/lib/api.ts`** - API client with TypeScript types

### Data Flow for Sync Operation
1. `SyncService.sync_all_videos()` calls `YouTubeService.get_channel_videos()`
2. For each video, `TranscriptService.fetch_transcript()` gets subtitles via `youtube-transcript-api`
3. Video metadata and cleaned transcripts stored in SQLite via SQLAlchemy ORM

### Configuration
Settings loaded via `pydantic-settings` from `.env`:
- `YOUTUBE_API_KEY` - Required for YouTube Data API v3
- `CHANNEL_ID` - Target YouTube channel
- `DATABASE_URL` - SQLite path (default: `sqlite:///./data/yt_assist.db`)

## Future Phases (Not Yet Implemented)

- **Phase 2:** RAG with ChromaDB embeddings and semantic search
- **Phase 3:** Style/tone modeling with fine-tuning support
- **Phase 4:** Content workflows (video wizard, series planner, clip finder)

See `docs/PRD.MD` and `docs/ARD.MD` for full specifications.
