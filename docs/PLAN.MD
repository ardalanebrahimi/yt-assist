# Implementation Plan

**Last Updated:** 2026-01-03

---

## Implementation Status Overview

| Milestone | Status | Description |
|-----------|--------|-------------|
| **Milestone 1** | ✅ Complete | Subtitle Ingestion MVP |
| **Milestone 2** | ❌ Not Started | RAG Layer |
| **Milestone 3** | ❌ Not Started | Style / Tone Modeling |
| **Milestone 4** | ✅ Complete | Whisper Transcription & Subtitle Management |
| **Milestone 4.5** | ✅ Complete | AI Dubbing (bonus feature) |
| **Milestone 5** | ❌ Not Started | YouTube Assistant Workflows |

---

## Milestone 1 – Subtitle Ingestion MVP ✅ COMPLETE

### 1.1 Implement YouTube Connector ✅
- List all videos for your channel
- For each video: store metadata in DB

### 1.2 Implement Subtitle Downloader ✅
- For each video, download primary subtitles (if available)
- Clean them (strip timestamps, merge lines)
- Store in DB as "Transcript"

### 1.3 Implement Sync Dashboard ✅
- React + shadcn/ui frontend
- All videos with status (synced / missing / error)
- Search and filter functionality

### 1.4 Implement Export ✅
- Export all transcripts to JSONL

> **After this:** You can upload this export into Custom GPT and Gemini.

---

## Milestone 2 – RAG Layer ⏳ NEXT

### 2.1 Implement Chunking Pipeline
- Split transcripts into time-based chunks with overlap

### 2.2 Implement Embeddings + Vector Store
- Generate embeddings for each chunk
- Store in ChromaDB with metadata

### 2.3 Implement RAG API
- `POST /ask` → question
- Internally:
  - Search in vector store
  - Call one base model
  - Answer + cite sources

### 2.4 Add Simple UI for Q&A + Citations
- Chat interface with source references
- Display video titles and timestamps

---

## Milestone 3 – Style / Tone Modeling

### 3.1 Add UI/CLI to Label Responses
- Mark good/bad answers for style

### 3.2 Implement Fine-Tuning Dataset Generation
- Scripts to generate training data from:
  - Transcripts
  - Your curated answers

### 3.3 Integrate with OpenAI Fine-Tuning Pipeline
- Upload training data
- Track fine-tuning jobs
- Version models

### 3.4 Teach Orchestrator to Use Fine-Tuned Model
- Call fine-tuned model instead of base model when "Ardalan voice" is enabled

---

## Milestone 4 – Whisper Transcription & Subtitle Management ✅ COMPLETE

### 4.1 Implement Whisper Integration ✅
- OpenAI Whisper API (~$0.006/min)
- Support Persian and English transcription
- Auto-detect FFmpeg installation

### 4.2 Implement Subtitle Upload to YouTube ✅
- OAuth 2.0 authentication
- Upload generated subtitles via YouTube Data API
- Replace existing captions option
- List and delete captions from UI

### 4.3 Implement Subtitle Quality Improvement ✅
- GPT-4o-mini cleanup service
- Preserve informal style and English technical terms
- Side-by-side diff view (GitHub-style)
- Save cleaned versions to database

### 4.4 Transcript Version Management ✅
- Track source: youtube / whisper / cleaned
- View all versions in UI
- Compare any two versions
- Upload selected version to YouTube

---

## Milestone 4.5 – AI Dubbing ✅ COMPLETE (Bonus Feature)

### 4.5.1 Translation Service ✅
- GPT-4o-mini for transcript translation
- Batch processing (50 segments per request)
- Support: EN, DE, FR, ES, AR, TR

### 4.5.2 Text-to-Speech Generation ✅
- OpenAI TTS API (tts-1 / tts-1-hd)
- 6 voices: alloy, echo, fable, onyx, nova, shimmer
- Timestamp-aligned audio segments

### 4.5.3 Audio Assembly ✅
- Combine TTS segments with proper timing
- Output MP3 files
- Play and download from UI

### Future Enhancements
- [ ] ElevenLabs voice cloning (use your own voice)
- [ ] Video + audio merge (output dubbed video file)
- [ ] Export translated SRT subtitles
- [ ] HD audio quality option

---

## Milestone 4.6 – Batch Processing with Real-time Progress ⏳ IN PROGRESS

### 4.6.1 Batch Operations UI
- Dedicated batch operations page
- Video selection with checkboxes
- Pagination (10 videos per page)
- Filter by status (needs whisper, needs cleanup, done)
- Select/deselect all functionality

### 4.6.2 Batch Plan Editor
- Preview what will be processed vs skipped
- Include/exclude individual videos before starting
- Choose operations per video (Whisper, Cleanup, or both)
- Cost and time estimates
- Modify plan before execution

### 4.6.3 Real-time Progress (SSE)
- Server-Sent Events for live updates
- Progress bar with percentage
- Per-video status: pending → processing → done/skipped/failed
- Current video highlighting
- Cancel operation (stops after current video)

### 4.6.4 Smart Skip Logic
- Auto-skip videos that already have Whisper transcript
- Auto-skip videos that already have cleaned transcript
- Show skipped count in summary
- Option to force re-process (override skip)

### 4.6.5 Cleanup Iteration
- Re-run cleanup with different settings
- Compare original vs cleaned versions
- Manual edit capability for cleaned transcripts

### API Endpoints
```
GET  /batch/whisper/candidates    # List videos needing Whisper
GET  /batch/cleanup/candidates    # List videos needing cleanup
GET  /batch/whisper/run?video_ids=...  # Run Whisper with SSE progress
GET  /batch/cleanup/run?video_ids=...  # Run cleanup with SSE progress
```

---

## Milestone 5 – YouTube Assistant Workflows + Experiments

### 5.1 Implement "New Video Wizard" Flow
- Input: idea or topic
- Output: overlap check, angle suggestion, outline, script

### 5.2 Implement "Series Planner"
- Input: series topic
- Output: current episodes summary, proposed next episodes

### 5.3 Implement "Clip Finder"
- Input: video ID
- Output: suggested clip ranges with timestamps and hooks

### 5.4 Implement Multi-Model Comparison View
- Side-by-side outputs from:
  - Your style model (+ RAG)
  - Base OpenAI
  - Gemini (optional)

---

## Technology Stack

### Backend
- **Framework:** FastAPI
- **Database:** SQLite + SQLAlchemy
- **APIs:** YouTube Data API v3, OpenAI (Whisper, GPT, TTS)

### Frontend
- **Framework:** React + TypeScript + Vite
- **UI:** shadcn/ui + Tailwind CSS
- **Icons:** Lucide React

### Services Implemented
| Service | File | Purpose |
|---------|------|---------|
| YouTube Connector | `app/services/youtube.py` | Fetch video metadata |
| Transcript Fetcher | `app/services/transcripts.py` | Download subtitles |
| Whisper Service | `app/services/whisper.py` | Transcribe audio |
| YouTube Captions | `app/services/youtube_captions.py` | Upload/manage captions |
| Transcript Cleanup | `app/services/transcript_cleanup.py` | GPT cleanup |
| Dubbing Service | `app/services/dubbing.py` | Translation + TTS |

---

## Next Steps

**Immediate:** Milestone 2 - RAG Layer
1. Implement chunking pipeline for transcripts
2. Set up ChromaDB for vector storage
3. Generate embeddings using text-embedding-3-small
4. Create search API endpoint
5. Build Q&A chat interface

**After RAG:** Milestone 3 or 5 based on priority
