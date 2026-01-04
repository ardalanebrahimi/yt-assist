# Implementation Plan

**Last Updated:** 2026-01-03

---

## Implementation Status Overview

| Milestone | Status | Description |
|-----------|--------|-------------|
| **Milestone 1** | ✅ Complete | Subtitle Ingestion MVP |
| **Milestone 2** | ✅ Complete | RAG Layer |
| **Milestone 3** | ❌ Not Started | Style / Tone Modeling |
| **Milestone 4** | ✅ Complete | Whisper Transcription & Subtitle Management |
| **Milestone 4.5** | ✅ Complete | AI Dubbing (bonus feature) |
| **Milestone 4.6** | ✅ Complete | Batch Processing |
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

## Milestone 2 – RAG Layer ✅ COMPLETE

### 2.1 Implement Chunking Pipeline ✅
- Split transcripts into character-based chunks with overlap (500 chars, 100 overlap)
- Sentence boundary detection for clean breaks

### 2.2 Implement Embeddings + Vector Store ✅
- OpenAI text-embedding-3-small for embeddings
- FAISS for vector storage (ChromaDB had compatibility issues with Python 3.13)
- Persistent storage to disk

### 2.3 Implement RAG API ✅
- `POST /rag/ask` - Ask questions with RAG
- `POST /rag/search` - Semantic search across transcripts
- `POST /rag/index/all` - Index all videos
- `POST /rag/index/{video_id}` - Index single video
- `GET /rag/stats` - Get index statistics
- `GET /rag/videos/indexed` - List indexed videos
- `DELETE /rag/index` - Clear index

### 2.4 Add Simple UI for Q&A + Citations ✅
- Chat interface with conversation history
- Index management panel (index all, clear, stats)
- Source citations with video links
- Real-time response streaming

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

## Milestone 4.6 – Batch Processing with Real-time Progress ✅ COMPLETE

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

## Milestone 5 – Content Automation & AI Assistants

### 5.1 Content Creation Assistants

#### 5.1.1 "New Video Wizard" Flow
- Input: idea or topic
- Output: overlap check, angle suggestion, outline, script

#### 5.1.2 "Series Planner"
- Input: series topic
- Output: current episodes summary, proposed next episodes

#### 5.1.3 "Clip Finder" / Shorts Generator
- Input: video ID
- Output: suggested clip ranges with timestamps and hooks
- Auto-generate vertical shorts with captions
- Post directly to YouTube Shorts

### 5.2 Social Media Automation

#### 5.2.1 LinkedIn Automation
- Generate post from video transcript (key insights, tips)
- Create carousel posts from video chapters
- Schedule and auto-post via LinkedIn API
- Track engagement metrics

#### 5.2.2 Instagram Automation
- Generate reels from video clips
- Create carousel posts with key points
- Auto-generate captions and hashtags
- Post via Instagram Graph API

#### 5.2.3 Telegram Channel
- Auto-post video announcements
- Share transcripts and summaries
- Daily/weekly content digests
- Telegram Bot API integration

### 5.3 Content Repurposing Pipeline

#### 5.3.1 Video → Multi-Platform Content
- Video → Blog post (Markdown/HTML)
- Video → Twitter/X thread
- Video → LinkedIn article
- Video → Newsletter content

#### 5.3.2 Shorts/Clips Pipeline
- Auto-detect highlight moments (high engagement potential)
- Generate vertical video with burned-in captions
- A/B test different hooks/thumbnails
- Batch upload to YouTube Shorts, Instagram Reels, TikTok

### 5.4 AI Agents

#### 5.4.1 Comment Responder Agent
- Monitor YouTube comments
- Draft responses in your style (using fine-tuned model)
- Queue for approval or auto-respond
- Handle common questions via RAG

#### 5.4.2 Analytics Reporter Agent
- Weekly performance reports
- Identify trending topics in your niche
- Suggest content gaps and opportunities
- Compare your content vs competitors

#### 5.4.3 Content Scheduler Agent
- Optimal posting time recommendations
- Cross-platform scheduling
- Content calendar management
- Reminder notifications

### 5.5 Multi-Model Comparison View
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
| RAG Service | `app/services/rag.py` | Embeddings, search, Q&A |

---

## Next Steps

**Current:** Milestone 5 - Content Automation & AI Assistants

Suggested implementation order:
1. **5.1 Content Creation Assistants** - New Video Wizard, Series Planner, Clip Finder
2. **5.2.3 Telegram Channel** - Easiest social platform to start (Bot API is simple)
3. **5.2.1 LinkedIn Automation** - High value for professional content
4. **5.3 Content Repurposing** - Video → Blog/Thread/Article
5. **5.4 AI Agents** - Comment responder, Analytics reporter
6. **5.2.2 Instagram** - More complex (requires Meta Business account)

**Later:** Milestone 3 (Style/Tone Modeling) - requires labeled training data from using the system
