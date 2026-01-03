# Ardalan YouTube AI Assistant – PRD

**Version:** v1.0
**Owner:** Ardalan
**Last Updated:** 2026-01-01

---

## 1. Product Overview

Ardalan YouTube AI Assistant is a personal internal tool for managing and leveraging all content from Ardalan's YouTube channel.

The assistant should:

- Understand the content, structure, and evolution of the channel.
- Speak and think in Ardalan's tone and mindset.
- Support ideation, planning, scripting, and optimization of future videos.

The product is not a public SaaS; it is a private productivity tool for Ardalan only (with possible future extension).

---

## 2. Goals & Non-Goals

### Goals

- Centralize all YouTube subtitles and metadata in a structured, queryable library.
- Provide an AI assistant that:
  - Writes and talks in Ardalan's style.
  - Uses existing videos as a knowledge base.
- Support content workflows:
  - Topic ideation.
  - Script writing.
  - Follow-up video planning.
  - Clip/shorts suggestion.
- Enable experimentation with:
  - Multiple model vendors.
  - RAG vs non-RAG setups.
  - Fine-tuned vs base models.

### Non-Goals (for now)

- No public-facing user interface or user accounts.
- No direct publishing to YouTube (upload/publish is manual).
- No automated video editing.
- No monetization features.
- No multi-user collaboration; this is single-user (Ardalan) only.

---

## 3. Target Users & Use Cases

**Primary User:** Ardalan (YouTube creator, technical educator).

### Core Use Cases

#### Subtitle Library Management

- "Sync all subtitles from my channel into the system."
- "Show me which videos are missing subtitles or not yet synced."
- "Export all transcripts for backup / other tools."

#### Knowledge Query

- "What have I already said about [X] across all my videos?"
- "List all videos where I talk about agentic coding."
- "Summarize my main opinions on microservices vs modular monolith."

#### Content Ideation

- "Suggest 5 video ideas that logically follow my episode [Title]."
- "Given my last 10 videos, what topics are missing in this series?"
- "Propose a new series based on my popular topics."

#### Script & Outline Creation

- "Write a script outline in my style for a 10–15 minute video on [Topic]."
- "Turn this outline into a full script that sounds like me."
- "Shorten this script into a 60-second YouTube Short in my tone."

#### Channel Strategy & Analysis

- "Analyze my existing catalog and suggest which topics I should revisit."
- "Group my videos into themes/series and propose what's missing."
- "Based on my current content, what could be a good 'live' session topic?"

#### Clip / Shorts Suggestion

- "From video [ID/URL], propose 5 short clip candidates with timestamps."
- "Find emotionally strong or high-impact segments I can turn into shorts."

#### Experimentation & Comparison

- "Run this same request with:
  - my style model + RAG,
  - base OpenAI model,
  - Gemini model,
  - and show me the three outputs side by side."

---

## 4. Scope by Phase

### Phase 1 – Subtitle Ingestion MVP

#### In Scope

- Connect to Ardalan's YouTube channel (read-only).
- Fetch:
  - List of all videos (id, title, description, tags, publish date).
  - Available subtitles for each video (prefer primary language, but support multiple).
- Clean and store subtitles as full transcripts.
- Track sync status:
  - "Synced / Not synced / Error."
- Manual trigger:
  - "Sync all now."
  - "Sync this specific video."
- Simple view of:
  - All videos with basic metadata.
  - Status of subtitles.

#### Out of Scope for Phase 1

- RAG search.
- Script generation.
- Style fine-tuning.
- Clip detection.

### Phase 2 – Knowledge & RAG

#### In Scope

- Ability to ask natural language questions about existing videos.
- System should:
  - Retrieve relevant passages from transcripts.
  - Generate an answer citing which videos/passages it used.
- Basic UI:
  - "Question input."
  - "Answer."
  - "List of referenced videos + timestamps."
- Search by:
  - Keyword/topic.
  - Video title.
  - Time range.
- Basic analytics:
  - Count of videos per topic/tag (rough).

### Phase 3 – Style / Tone Modeling

#### In Scope

- Generate answers and scripts in Ardalan's tone.
- Allow user to:
  - Provide a short style description (e.g., "direct, practical, little fluff, mix of high-level & concrete examples, humor but not cringe").
  - Provide example answers to calibrate "ideal voice."
- Use this tone for:
  - Outlines.
  - Full scripts.
  - Explanations.

#### Functional Requirements

- Setting to toggle:
  - "Ardalan voice ON/OFF."
- Ability to run:
  - Same prompt in 2 modes: "Ardalan style" vs "Generic."
- Evaluation support:
  - User can label output as "good style" / "off-style" (for future iterations).

### Phase 4 – Whisper Transcription & Subtitle Management

#### In Scope

- Transcribe videos without YouTube auto-subtitles using OpenAI Whisper API
- Support for videos uploaded before YouTube added Persian ASR (pre-Aug 2023)
- Upload generated subtitles to YouTube via API
- Review and edit subtitles before publishing
- Option to improve/replace existing auto-generated subtitles with Whisper output

#### Cost Estimate

- OpenAI Whisper API: ~$0.006/minute
- 30-minute video: ~$0.18
- Alternative: Local Whisper (free, requires GPU for speed)

---

### Phase 4.5 – AI Dubbing (Bonus Feature)

#### In Scope

- Translate transcripts to other languages (EN, DE, FR, ES, AR, TR)
- Generate dubbed audio using OpenAI TTS
- Multiple voice options (6 voices)
- Download dubbed audio files
- Play audio in browser

---

### Phase 4.6 – Batch Processing with Real-time Progress

#### In Scope

- Batch Whisper transcription for multiple videos
- Batch GPT cleanup for multiple videos
- Real-time progress visibility via Server-Sent Events (SSE)
- Video selection with checkboxes and pagination
- Modify batch plan before execution (include/exclude videos)
- Smart skip logic (don't re-process already done videos)
- Cost and time estimates before starting
- Cancel operation capability

#### User Stories

- "I want to transcribe all my old videos at once and see the progress"
- "I want to clean up all my transcripts in one batch operation"
- "I want to choose which videos to include in the batch"
- "I want to see which videos will be skipped because they're already done"
- "I want to stop the batch operation if something goes wrong"

---

### Phase 5 – YouTube Assistant Workflows

#### In Scope

**End-to-end flows:**

1. **New Video Wizard**
   - Input: idea or topic.
   - Output:
     - Check overlap with existing videos.
     - Suggest angle that fits your narrative.
     - Outline → script in your style.

2. **Series Planner**
   - Input: series topic (e.g., Agentic Coding).
   - Output:
     - Current episodes summary.
     - Proposed next 3–5 episodes with titles and main bullets.

3. **Clip Finder**
   - Input: video id.
   - Output:
     - 3–10 suggested clip ranges (timestamp start–end).
     - One-sentence "hook" text for each clip.

4. **Strategic Suggestions**
   - Input: "Analyze my channel for gaps / opportunities."
   - Output:
     - High-level observations.
     - Possible next themes/series.

**Multi-model comparison:**

- Option to choose:
  - "Use my model."
  - "Use OpenAI base model."
  - "Use Gemini."
- Comparison UI (side by side).

---

## 5. Content & Data

**Source of truth:** Ardalan's YouTube channel.

**Data stored:**

- Video metadata (IDs, titles, descriptions, tags, publish dates, URLs).
- Subtitles/transcripts (possibly multiple languages).
- Internal annotations:
  - Topics, themes, series.
  - User feedback (liked outputs, bad outputs).

**Privacy:** All data is private to Ardalan. No sharing with others.

---

## 6. Success Metrics (internal / qualitative)

- Ardalan actually uses the assistant weekly.
- Time to write a script reduced significantly.
- Reduced repetition of topics across videos.
- Increased confidence in channel strategy (less "what should I do next?").
- Subjective score: "How much does this output feel like me?" (target ≥ 8/10 on average).

---

## 7. Risks & Open Questions

- Vendor lock-in vs complexity of supporting many providers.
- Cost of using external APIs at scale.
- Overfitting style model (too rigid, less flexible).
- Keeping transcripts synced if channel grows quickly.
