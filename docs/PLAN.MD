# Implementation Plan

---

## Milestone 1 – Subtitle Ingestion MVP

### 1.1 Implement YouTube Connector

- List all videos for your channel
- For each video: store metadata in DB

### 1.2 Implement Subtitle Downloader

- For each video, download primary subtitles (if available)
- Clean them (strip timestamps, merge lines)
- Store in DB as "Transcript"

### 1.3 Implement Sync Dashboard

- Page/CLI listing:
  - All videos
  - Subtitles status (synced / missing / error)

### 1.4 Implement Export

- Button/command: export all transcripts to:
  - Single JSONL
  - Or zipped plain text files

> **After this:** You can upload this export into Custom GPT and Gemini.

---

## Milestone 2 – RAG Layer

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

## Milestone 4 – Whisper Transcription & Subtitle Management

### 4.1 Implement Whisper Integration

- For videos without YouTube auto-subtitles (pre-Aug 2023)
- Use OpenAI Whisper API (~$0.006/min) or local Whisper
- Support Persian and English transcription

### 4.2 Implement Subtitle Upload to YouTube

- Use YouTube Data API to upload generated subtitles
- Set language and publish status
- Track which videos have been processed

### 4.3 Implement Subtitle Quality Improvement

- Compare Whisper output with existing auto-generated subtitles
- Option to replace/improve existing subtitles
- Review UI before publishing to YouTube

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
