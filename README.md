# YT-Assist

Personal YouTube AI Assistant for managing and leveraging YouTube channel content.

## Features (Milestone 1)

- Sync all videos and transcripts from your YouTube channel
- View video library with sync status tracking
- Export transcripts as JSONL or ZIP files
- Clean and store both raw and processed transcripts

## Requirements

- Python 3.11+
- YouTube Data API v3 key

## Setup

1. **Clone and create virtual environment:**
   ```bash
   git clone <repo-url>
   cd yt-assist
   python -m venv venv
   ```

2. **Install dependencies:**
   ```bash
   # Windows
   ./venv/Scripts/pip install -r requirements.txt

   # Unix/Mac
   venv/bin/pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add:
   - `YOUTUBE_API_KEY` - Get from [Google Cloud Console](https://console.cloud.google.com/) (enable YouTube Data API v3)
   - `CHANNEL_ID` - Your YouTube channel ID

## Running

**Start the API server:**
```bash
./venv/Scripts/uvicorn app.main:app --reload
```

**Start the UI** (in a separate terminal):
```bash
./venv/Scripts/streamlit run ui/app.py
```

Open http://localhost:8501 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/videos` | GET | List all videos |
| `/api/videos/{id}` | GET | Get video details with transcripts |
| `/api/sync/all` | POST | Sync all videos from channel |
| `/api/sync/video/{id}` | POST | Sync single video |
| `/api/sync/status` | GET | Get sync status summary |
| `/api/export/jsonl` | GET | Export transcripts as JSONL |
| `/api/export/zip` | GET | Export transcripts as ZIP |

API docs available at http://localhost:8000/docs

## Project Structure

```
yt-assist/
├── app/                  # FastAPI backend
│   ├── api/routes/       # API endpoints
│   ├── db/               # SQLAlchemy models
│   └── services/         # Business logic
├── ui/                   # Streamlit frontend
│   └── pages/            # UI pages
├── data/                 # SQLite database
└── docs/                 # PRD and Architecture docs
```

## Documentation

- [PRD.MD](docs/PRD.MD) - Product Requirements Document
- [ARD.MD](docs/ARD.MD) - Architecture Reference Document

## Roadmap

- [x] **Phase 1:** Subtitle Ingestion MVP
- [ ] **Phase 2:** Knowledge & RAG (semantic search)
- [ ] **Phase 3:** Style/Tone Modeling
- [ ] **Phase 4:** YouTube Assistant Workflows
