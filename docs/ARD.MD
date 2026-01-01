# Ardalan YouTube AI Assistant – ARD

**Version:** v1.0
**Last Updated:** 2026-01-01

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interface                                  │
│                         (Streamlit Web App)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LLM Orchestrator                                  │
│                   (Request routing, RAG decision, style)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                          │                    │
              ┌───────────┘                    └───────────┐
              ▼                                            ▼
┌─────────────────────────────┐              ┌─────────────────────────────────┐
│       RAG Service           │              │     LLM Provider Abstraction    │
│  (Embeddings + Vector DB)   │              │   (OpenAI / Claude / Gemini)    │
└─────────────────────────────┘              └─────────────────────────────────┘
              │                                            │
              └───────────────────┬────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Core Data Store                                    │
│                    (SQLite → PostgreSQL migration path)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                  ▲
                                  │
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Ingestion Service                                   │
│                  (YouTube Data API v3 + Subtitles)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Components

### 2.1 Ingestion Service

**Responsibility:** Fetch video metadata and subtitles from YouTube.

**Technology:**
- Python library: `google-api-python-client` for YouTube Data API v3
- `youtube-transcript-api` for fetching auto-generated and manual subtitles

**Functionality:**
- Authenticate using OAuth 2.0 (for private channel access) or API key (for public data)
- Fetch all videos from a channel (paginated)
- Retrieve available subtitle tracks per video
- Download and parse subtitles (VTT/SRT format)
- Clean transcript text (remove timestamps, speaker tags if needed)
- Store raw + cleaned versions
- Track sync status per video

**API Endpoints:**
```
POST /api/sync/all              # Sync all videos from channel
POST /api/sync/video/{video_id} # Sync specific video
GET  /api/sync/status           # Get sync status summary
```

---

### 2.2 Core Data Store

**Responsibility:** Persist all structured data.

**Technology:**
- **Phase 1:** SQLite (local, zero-config, single-file)
- **Future:** PostgreSQL (when scaling or needing pgvector)

**ORM:** SQLAlchemy (supports both SQLite and PostgreSQL)

#### Data Models

```python
class Video:
    id: str                    # YouTube video ID (primary key)
    title: str
    description: str
    published_at: datetime
    duration_seconds: int
    tags: list[str]            # JSON array
    thumbnail_url: str
    channel_id: str
    view_count: int            # Optional, from API
    sync_status: str           # "pending" | "synced" | "error"
    sync_error: str | None
    synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

class Transcript:
    id: int                    # Auto-increment
    video_id: str              # FK to Video
    language_code: str         # e.g., "en", "fa"
    is_auto_generated: bool
    raw_content: str           # Original with timestamps
    clean_content: str         # Plain text, cleaned
    created_at: datetime

class TranscriptChunk:
    id: int                    # Auto-increment
    transcript_id: int         # FK to Transcript
    video_id: str              # Denormalized for quick access
    chunk_index: int           # Order within transcript
    content: str               # Chunk text
    start_time: float          # Seconds from video start
    end_time: float            # Seconds from video start
    token_count: int           # For context window management
    embedding_id: str | None   # Reference to vector store
    created_at: datetime

class StyleFeedback:
    id: int
    prompt: str
    response: str
    model_used: str
    rating: int                # 1-10 scale
    feedback_notes: str | None
    created_at: datetime
```

---

### 2.3 RAG Service

**Responsibility:** Chunk transcripts, generate embeddings, perform semantic search.

**Technology:**
- **Embedding Model:** `text-embedding-3-small` (OpenAI) - good balance of cost/quality
- **Vector Store (Local):** ChromaDB (file-based, easy setup)
- **Future Options:** pgvector (PostgreSQL), Azure AI Search, Pinecone

#### Chunking Strategy

**Approach:** Time-based chunking with overlap

```python
CHUNK_CONFIG = {
    "target_duration_seconds": 60,    # ~60 seconds of speech per chunk
    "max_tokens": 500,                 # Hard limit for context
    "overlap_seconds": 10,             # Overlap for context continuity
    "min_chunk_tokens": 50,            # Don't create tiny chunks
}
```

**Rationale:**
- YouTube subtitles have natural timestamp boundaries
- 60-second chunks ≈ 150-200 words ≈ good semantic unit
- Overlap ensures we don't split mid-thought
- Preserves timestamp for citation ("at 3:45 in video X")

#### Embedding Pipeline

```
Transcript → Split by timestamps → Merge to target duration
           → Generate embedding → Store in ChromaDB with metadata
```

**Metadata stored with each vector:**
```python
{
    "video_id": "abc123",
    "video_title": "...",
    "chunk_index": 5,
    "start_time": 180.0,
    "end_time": 240.0,
    "transcript_id": 42
}
```

**API Endpoints:**
```
POST /api/rag/embed/video/{video_id}  # Embed single video's transcript
POST /api/rag/embed/all               # Embed all unembedded transcripts
POST /api/rag/search                  # Semantic search
     Body: { "query": "...", "top_k": 5, "filters": {...} }
```

---

### 2.4 LLM Orchestrator

**Responsibility:** Route requests, decide RAG usage, apply style, manage conversation.

**Technology:** Python + LangChain (for chaining and memory)

#### Request Flow

```
User Query → Classify Intent → RAG Decision → Build Prompt → Call LLM → Format Response
```

**Intent Classification:**
| Intent | RAG Required | Example |
|--------|--------------|---------|
| `knowledge_query` | Yes | "What did I say about microservices?" |
| `content_ideation` | Yes | "Suggest follow-up videos to episode X" |
| `script_writing` | Optional | "Write a script about clean code" |
| `general_chat` | No | "How long should a YouTube intro be?" |

#### Style Prompting

**System Prompt Structure:**
```
You are an AI assistant that writes in Ardalan's voice and style.

STYLE GUIDELINES:
- Direct and practical, minimal fluff
- Mix high-level concepts with concrete examples
- Light humor, but professional
- Challenge assumptions when appropriate
- Reference real-world experience when relevant

CONTEXT FROM CHANNEL:
{rag_results if applicable}

USER REQUEST:
{user_query}
```

**Toggle Support:**
- `style_mode: "ardalan" | "generic"`
- When "generic", omit style guidelines

---

### 2.5 LLM Provider Abstraction

**Responsibility:** Unified interface for multiple LLM providers.

**Interface:**
```python
class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse: ...

    def get_available_models(self) -> list[str]: ...

class LLMResponse:
    content: str
    model: str
    usage: TokenUsage
    latency_ms: int
```

**Implementations:**
```python
class OpenAIProvider(LLMProvider):
    # Uses: gpt-4o, gpt-4o-mini, gpt-3.5-turbo
    # Fine-tuned models when available

class AnthropicProvider(LLMProvider):
    # Uses: claude-3-5-sonnet, claude-3-opus

class GeminiProvider(LLMProvider):
    # Uses: gemini-1.5-pro, gemini-1.5-flash
```

**Configuration:**
```python
# config.py
LLM_CONFIG = {
    "default_provider": "openai",
    "default_model": "gpt-4o-mini",
    "providers": {
        "openai": {
            "api_key": "${OPENAI_API_KEY}",
            "models": ["gpt-4o", "gpt-4o-mini"]
        },
        "anthropic": {
            "api_key": "${ANTHROPIC_API_KEY}",
            "models": ["claude-3-5-sonnet-20241022"]
        }
    }
}
```

---

### 2.6 Whisper Transcription Service (Phase 4)

**Responsibility:** Transcribe videos without YouTube subtitles and manage subtitle uploads.

**Problem Solved:**
- YouTube only added Persian ASR around August 2023
- Videos uploaded before that date have no auto-generated subtitles
- This service fills that gap using OpenAI Whisper

**Technology:**
- **OpenAI Whisper API** - Cloud-based, ~$0.006/minute
- **Local Whisper** (alternative) - Free, requires ffmpeg + ~1-6GB model

**Functionality:**
- Download audio from YouTube video (via yt-dlp)
- Send to Whisper API for transcription
- Store transcript in same format as YouTube subtitles
- Upload to YouTube via YouTube Data API (captions.insert)

**API Endpoints:**
```
POST /api/whisper/transcribe/{video_id}  # Transcribe video without subs
POST /api/whisper/upload/{video_id}       # Upload transcript to YouTube
GET  /api/whisper/status/{video_id}       # Check transcription status
```

**Data Flow:**
```
Video (no subs) → Download audio → Whisper API → Transcript
                                              → Store in DB
                                              → Upload to YouTube (optional)
```

**YouTube Caption Upload Requirements:**
- OAuth 2.0 authentication (not just API key)
- Scope: `youtube.force-ssl` for caption management
- Can set: language, name, isDraft status

---

### 2.7 Style / Fine-Tuning Pipeline (Phase 3)

**Responsibility:** Prepare data and manage fine-tuned models.

**Approach (Phase 3+):**

1. **Data Collection:**
   - Export transcripts as training examples
   - Collect `StyleFeedback` entries (good responses rated 8+)
   - Format as instruction/response pairs

2. **Training Data Format (OpenAI):**
```jsonl
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

3. **Fine-Tuning Jobs:**
   - Use OpenAI fine-tuning API
   - Track job IDs, costs, and resulting model names
   - Version models: `ft:gpt-4o-mini:ardalan:v1`, `v2`, etc.

4. **Evaluation:**
   - A/B test fine-tuned vs base models
   - Track style ratings over time

---

### 2.8 Experimentation Layer

**Responsibility:** Enable side-by-side model comparison.

**Features:**
- Run same prompt against multiple models
- Capture: response, latency, token usage, cost
- Store results for comparison UI

**API:**
```
POST /api/experiment/compare
Body: {
    "prompt": "...",
    "models": ["openai:gpt-4o", "anthropic:claude-3-5-sonnet"],
    "include_rag": true
}
Response: {
    "results": [
        { "model": "...", "response": "...", "latency_ms": 1200, "cost": 0.02 },
        ...
    ]
}
```

---

### 2.9 User Interface

**Responsibility:** Web interface for all user interactions.

**Technology:** Streamlit (Python-native, rapid development)

**Why Streamlit:**
- Single language (Python) for full stack
- Built-in components for chat, file upload, data display
- Easy to iterate during MVP phase
- Can migrate to React/Next.js later if needed

**Views:**

1. **Library View**
   - Table of all videos with metadata
   - Sync status indicators
   - Filter by date, status, search
   - Bulk sync actions

2. **Chat / Q&A View**
   - Chat interface
   - Toggle: "Use my style" on/off
   - Show referenced videos/timestamps in responses

3. **Content Workflows**
   - New Video Wizard (multi-step form)
   - Series Planner
   - Clip Finder

4. **Experiment View**
   - Model selector (multi-select)
   - Side-by-side response display
   - Rating/feedback capture

5. **Settings**
   - API key management
   - Style description editor
   - Sync preferences

---

## 3. Key Design Decisions

### 3.1 Why SQLite First?

| Factor | SQLite | PostgreSQL |
|--------|--------|------------|
| Setup complexity | None (file-based) | Requires server |
| Single-user performance | Excellent | Overkill |
| Migration effort | Low (via SQLAlchemy) | N/A |
| Vector support | Via ChromaDB | pgvector |

**Decision:** Start SQLite, migrate when needed.

### 3.2 Why ChromaDB for Vectors?

- Pure Python, embedded (no separate server)
- Persistent storage to disk
- Good enough for ~1000 videos × ~50 chunks = 50K vectors
- Easy migration path to cloud vector DBs

### 3.3 Chunking: Time-Based vs Semantic

| Approach | Pros | Cons |
|----------|------|------|
| Time-based | Preserves timestamps, predictable size | May split mid-sentence |
| Semantic | Coherent units | Loses timestamp precision |

**Decision:** Time-based with overlap. YouTube content naturally has timestamp boundaries, and citing "at 3:45" is valuable.

### 3.4 Embedding Model Choice

| Model | Dimensions | Cost | Quality |
|-------|------------|------|---------|
| text-embedding-3-small | 1536 | $0.02/1M tokens | Good |
| text-embedding-3-large | 3072 | $0.13/1M tokens | Better |
| text-embedding-ada-002 | 1536 | $0.10/1M tokens | Legacy |

**Decision:** `text-embedding-3-small` for cost efficiency. Can upgrade later.

---

## 4. Project Structure

```
yt-assist/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Settings and env vars
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── sync.py         # Ingestion endpoints
│   │   │   ├── videos.py       # Video CRUD
│   │   │   ├── rag.py          # Search endpoints
│   │   │   ├── chat.py         # LLM chat endpoints
│   │   │   └── experiment.py   # Comparison endpoints
│   │   └── deps.py             # Dependency injection
│   ├── services/
│   │   ├── __init__.py
│   │   ├── youtube.py          # YouTube API client
│   │   ├── transcripts.py      # Subtitle fetching/cleaning
│   │   ├── embeddings.py       # Chunking + embedding
│   │   ├── rag.py              # RAG search logic
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Provider interface
│   │   │   ├── openai.py
│   │   │   ├── anthropic.py
│   │   │   └── orchestrator.py # Main LLM logic
│   │   └── style.py            # Style prompt management
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy setup
│   │   ├── models.py           # ORM models
│   │   └── migrations/         # Alembic migrations
│   └── core/
│       ├── __init__.py
│       └── exceptions.py
├── ui/
│   ├── app.py                  # Streamlit entry
│   ├── pages/
│   │   ├── 1_Library.py
│   │   ├── 2_Chat.py
│   │   ├── 3_Workflows.py
│   │   ├── 4_Experiments.py
│   │   └── 5_Settings.py
│   └── components/
│       └── ...
├── data/
│   ├── yt_assist.db            # SQLite database
│   └── chroma/                 # ChromaDB persistence
├── tests/
│   └── ...
├── docs/
│   ├── PRD.MD
│   └── ARD.MD
├── .env                        # API keys (gitignored)
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 5. Authentication & Security

**Single-User Model:**
- No user accounts needed
- Optional: simple password protection for web UI (Streamlit auth or basic HTTP auth)
- API keys stored in `.env` file (never committed)

**YouTube OAuth:**
- Required if accessing private/unlisted videos
- Store refresh token securely
- For public channel data, API key is sufficient

---

## 6. Logging & Observability

**Logging:**
- Structured JSON logging (Python `structlog`)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Key events: sync operations, LLM calls, errors

**Metrics to Track:**
- Sync success/failure rate
- LLM latency per provider/model
- Token usage and cost
- RAG retrieval quality (manual review)

**Storage:**
- Local: log files with rotation
- Future: Azure Application Insights or similar

---

## 7. Cost Estimation (Monthly)

| Service | Usage Estimate | Cost |
|---------|----------------|------|
| OpenAI Embeddings | 50K chunks × 500 tokens | ~$0.50 |
| OpenAI GPT-4o-mini | 1000 requests × 2K tokens | ~$1.50 |
| OpenAI GPT-4o | 100 requests × 2K tokens | ~$2.00 |
| ChromaDB | Local | $0 |
| SQLite | Local | $0 |
| **Total (Local)** | | **~$4/month** |

*Costs scale with usage. Fine-tuning adds one-time costs (~$5-20 per job).*

---

## 8. Migration Paths

### SQLite → PostgreSQL
1. Set up PostgreSQL instance
2. Update `DATABASE_URL` in config
3. Run Alembic migrations
4. Data migration script (export/import)

### ChromaDB → pgvector
1. Add `pgvector` extension to PostgreSQL
2. Create embedding column in `TranscriptChunk`
3. Re-run embedding pipeline
4. Update RAG service to use pgvector queries

### ChromaDB → Azure AI Search
1. Create Azure AI Search resource
2. Define index schema matching current metadata
3. Bulk upload embeddings
4. Update RAG service client

---

## 9. Phase 1 Implementation Checklist

- [ ] Project setup (Python, FastAPI, dependencies)
- [ ] Database models and migrations
- [ ] YouTube API integration (video list)
- [ ] Subtitle fetching and cleaning
- [ ] Basic Streamlit UI (library view)
- [ ] Sync endpoints and status tracking
- [ ] Environment configuration
- [ ] Basic error handling and logging
