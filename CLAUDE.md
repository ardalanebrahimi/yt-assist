# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YT-Assist is a personal YouTube AI assistant for managing channel content, syncing video metadata and transcripts, and (in future phases) providing RAG-based Q&A and script generation in the channel owner's style.

**Current Phase:** Milestone 1 - Subtitle Ingestion MVP

## Commands

### Development Setup
```bash
python -m venv venv
./venv/Scripts/pip install -r requirements.txt  # Windows
# or: venv/bin/pip install -r requirements.txt  # Unix
```

### Running the Application
```bash
# Start FastAPI backend (port 8000)
./venv/Scripts/uvicorn app.main:app --reload

# Start Streamlit UI (port 8501) - in separate terminal
./venv/Scripts/streamlit run ui/app.py
```

### Linting
```bash
./venv/Scripts/ruff check app/ ui/
./venv/Scripts/black --check app/ ui/
```

## Architecture

```
UI (Streamlit) → FastAPI Backend → Services → SQLite DB
     ↓                                ↓
  ui/app.py                    app/services/
  ui/pages/                    - youtube.py (YouTube Data API)
                               - transcripts.py (subtitle fetching)
                               - sync.py (orchestration)
```

### Key Layers

- **`app/api/routes/`** - FastAPI endpoints: `/api/videos`, `/api/sync`, `/api/export`
- **`app/services/`** - Business logic: YouTubeService, TranscriptService, SyncService
- **`app/db/models.py`** - SQLAlchemy models: Video, Transcript
- **`ui/pages/1_Library.py`** - Main Streamlit page for video management

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
