import axios from "axios"

const API_BASE = "http://127.0.0.1:8000/api"

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
})

// Types
export interface Video {
  id: string
  title: string
  description: string | null
  published_at: string | null
  duration_seconds: number | null
  tags: string[]
  thumbnail_url: string | null
  channel_id: string
  view_count: number | null
  sync_status: "pending" | "synced" | "error"
  sync_error: string | null
  synced_at: string | null
  created_at: string
  updated_at: string
  has_transcript: boolean
}

export interface Transcript {
  id: number
  language_code: string
  is_auto_generated: boolean
  source: "youtube" | "whisper" | "cleaned"
  raw_content: string  // With timestamps
  clean_content: string  // Plain text
  created_at: string
}

export interface VideoDetail extends Video {
  transcripts: Transcript[]
}

export interface VideoListResponse {
  items: Video[]
  total: number
  page: number
  page_size: number
}

export interface SyncStatus {
  total_videos: number
  synced: number
  pending: number
  errors: number
}

export interface SyncResult {
  video_id: string
  success: boolean
  error: string | null
  has_transcript: boolean
}

export interface SyncAllResponse {
  message: string
  results: SyncResult[]
  summary: SyncStatus
}

// API Functions
export async function getVideos(params: {
  page?: number
  page_size?: number
  status?: string
  search?: string
}): Promise<VideoListResponse> {
  const { data } = await api.get("/videos", { params })
  return data
}

export async function getVideo(videoId: string): Promise<VideoDetail> {
  const { data } = await api.get(`/videos/${videoId}`)
  return data
}

export async function getSyncStatus(): Promise<SyncStatus> {
  const { data } = await api.get("/sync/status")
  return data
}

export async function syncAllVideos(): Promise<SyncAllResponse> {
  const { data } = await api.post("/sync/all", {})
  return data
}

export async function syncVideo(videoId: string): Promise<SyncResult> {
  const { data } = await api.post(`/sync/video/${videoId}`)
  return data
}

export async function getExportStats(): Promise<{
  total_videos: number
  synced_videos: number
  total_transcripts: number
  total_words: number
  exportable: boolean
}> {
  const { data } = await api.get("/export/stats")
  return data
}

// Whisper API Types
export interface WhisperCandidate {
  id: string
  title: string
  duration_seconds: number | null
  published_at: string | null
  estimated_cost: number
}

export interface WhisperCandidatesResponse {
  items: WhisperCandidate[]
  total: number
  total_estimated_cost: number
}

export interface TranscribeResponse {
  video_id: string
  success: boolean
  message: string
  language_code?: string
  transcript_id?: number
  cost_estimate?: number
}

export interface YouTubeAuthStatus {
  authenticated: boolean
  message: string
}

// Whisper API Functions
export async function getWhisperCandidates(): Promise<WhisperCandidatesResponse> {
  const { data } = await api.get("/whisper/candidates")
  return data
}

export async function transcribeVideo(
  videoId: string,
  language: string = "fa"
): Promise<TranscribeResponse> {
  const { data } = await api.post(`/whisper/transcribe/${videoId}`, { language })
  return data
}

export async function getCostEstimate(videoId: string): Promise<{
  video_id: string
  duration_seconds: number
  duration_minutes: number
  estimated_cost_usd: number
}> {
  const { data } = await api.get(`/whisper/cost-estimate/${videoId}`)
  return data
}

// Transcript API Types
export interface CleanupResponse {
  video_id: string
  success: boolean
  message: string
  original?: string
  cleaned?: string
  changes_summary?: string
  cost_estimate?: number
}

// Transcript API Functions
export async function cleanupTranscript(
  videoId: string,
  language: string = "fa",
  preserveTimestamps: boolean = true
): Promise<CleanupResponse> {
  const { data } = await api.post(`/transcripts/${videoId}/cleanup`, {
    language,
    preserve_timestamps: preserveTimestamps,
  })
  return data
}

export async function saveCleanedTranscript(
  videoId: string,
  cleanedContent: string,
  language: string = "fa"
): Promise<{ video_id: string; transcript_id: number; success: boolean; message: string }> {
  const { data } = await api.post(`/transcripts/${videoId}/save`, {
    cleaned_content: cleanedContent,
    language,
  })
  return data
}

export async function uploadToYouTube(
  videoId: string,
  language: string = "fa",
  isDraft: boolean = false
): Promise<{ video_id: string; success: boolean; message: string; caption_id?: string }> {
  const { data } = await api.post(`/transcripts/${videoId}/youtube/upload`, {
    language,
    is_draft: isDraft,
  })
  return data
}

export async function uploadCleanedToYouTube(
  videoId: string,
  cleanedContent: string,
  language: string = "fa",
  isDraft: boolean = false
): Promise<{ video_id: string; success: boolean; message: string; caption_id?: string }> {
  const { data } = await api.post(`/transcripts/${videoId}/youtube/upload-content`, {
    cleaned_content: cleanedContent,
    language,
    is_draft: isDraft,
  })
  return data
}

export async function getYouTubeAuthStatus(): Promise<YouTubeAuthStatus> {
  const { data } = await api.get("/transcripts/youtube/auth-status")
  return data
}

export async function authenticateYouTube(): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post("/transcripts/youtube/authenticate")
  return data
}

// YouTube Captions Management
export interface YouTubeCaption {
  id: string
  language: string
  name: string
  is_auto_synced: boolean
  is_draft: boolean
  track_kind: string
}

export async function listYouTubeCaptions(videoId: string): Promise<YouTubeCaption[]> {
  const { data } = await api.get(`/transcripts/${videoId}/youtube/captions`)
  return data.captions || []
}

export async function deleteYouTubeCaption(videoId: string, captionId: string): Promise<boolean> {
  const { data } = await api.delete(`/transcripts/${videoId}/youtube/captions/${captionId}`)
  return data.success
}

// Dubbing API Types
export interface DubbingVoice {
  id: string
  description: string
}

export interface DubbingCostEstimate {
  video_id: string
  segments: number
  source_characters: number
  estimated_translated_characters: number
  translation_cost_usd: number
  tts_cost_usd: number
  total_cost_usd: number
}

export interface DubbingResponse {
  video_id: string
  success: boolean
  message: string
  audio_url?: string
  duration_seconds?: number
  segments_count?: number
  source_language?: string
  target_language?: string
}

export interface DubFile {
  filename: string
  language: string
  url: string
  size_bytes: number
}

// Dubbing API Functions
export async function getDubbingVoices(): Promise<{
  voices: DubbingVoice[]
  models: { id: string; description: string }[]
  supported_target_languages: { code: string; name: string }[]
}> {
  const { data } = await api.get("/dubbing/voices")
  return data
}

export async function getDubbingCostEstimate(
  videoId: string,
  targetLanguage: string = "en"
): Promise<DubbingCostEstimate> {
  const { data } = await api.get(`/dubbing/${videoId}/cost-estimate`, {
    params: { target_language: targetLanguage },
  })
  return data
}

export async function createDub(
  videoId: string,
  options: {
    source_language?: string
    target_language?: string
    voice?: string
    model?: string
    transcript_id?: number
  } = {}
): Promise<DubbingResponse> {
  const { data } = await api.post(`/dubbing/${videoId}/create`, {
    source_language: options.source_language || "fa",
    target_language: options.target_language || "en",
    voice: options.voice || "nova",
    model: options.model || "tts-1",
    transcript_id: options.transcript_id,
  })
  return data
}

export async function listDubs(videoId: string): Promise<DubFile[]> {
  const { data } = await api.get(`/dubbing/${videoId}/list`)
  return data.dubs || []
}

// Batch Processing API Types
export interface BatchCandidate {
  id: string
  title: string
  duration_seconds?: number
  estimated_cost?: number
  source?: string
  char_count?: number
}

export interface BatchCandidatesResponse {
  candidates: BatchCandidate[]
  already_done: { id: string; title: string }[]
  summary: {
    total_candidates: number
    already_done: number
    total_duration_minutes?: number
    estimated_total_cost: number
  }
}

export interface BatchProgressEvent {
  current: number
  total: number
  video_id: string
  title: string
  status: "pending" | "processing" | "done" | "skipped" | "failed"
  message: string
  completed: number
  skipped: number
  failed: number
}

export interface BatchCompleteEvent {
  total: number
  completed: number
  skipped: number
  failed: number
  message: string
}

export interface VideoStatusSummary {
  summary: {
    total_videos: number
    with_youtube_subtitle: number
    with_whisper: number
    with_cleaned: number
    no_transcript: number
    needs_whisper: number
    needs_cleanup: number
    fully_processed: number
  }
  videos: {
    id: string
    title: string
    duration_seconds: number | null
    has_youtube: boolean
    has_whisper: boolean
    has_cleaned: boolean
  }[]
}

// Batch Processing API Functions
export async function getVideoStatusSummary(): Promise<VideoStatusSummary> {
  const { data } = await api.get("/batch/status/summary")
  return data
}

export async function getBatchWhisperCandidates(): Promise<BatchCandidatesResponse> {
  const { data } = await api.get("/batch/whisper/candidates")
  return data
}

export async function getBatchCleanupCandidates(): Promise<BatchCandidatesResponse> {
  const { data } = await api.get("/batch/cleanup/candidates")
  return data
}

export function createBatchWhisperStream(
  videoIds?: string[],
  language: string = "fa"
): EventSource {
  const params = new URLSearchParams()
  if (videoIds && videoIds.length > 0) {
    params.set("video_ids", videoIds.join(","))
  }
  params.set("language", language)
  return new EventSource(`${API_BASE}/batch/whisper/run?${params.toString()}`)
}

export function createBatchCleanupStream(
  videoIds?: string[],
  language: string = "fa",
  preserveTimestamps: boolean = true
): EventSource {
  const params = new URLSearchParams()
  if (videoIds && videoIds.length > 0) {
    params.set("video_ids", videoIds.join(","))
  }
  params.set("language", language)
  params.set("preserve_timestamps", preserveTimestamps.toString())
  return new EventSource(`${API_BASE}/batch/cleanup/run?${params.toString()}`)
}

// RAG API Types and Functions

export interface AskResponse {
  answer: string
  sources: {
    video_id: string
    title: string
    url: string
  }[]
  chunks_used: number
}

export interface SearchResult {
  text: string
  video_id: string
  video_title: string
  score: number
  rank: number
}

export interface IndexStats {
  total_chunks: number
  videos_indexed: number
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
}

export interface IndexResult {
  videos_processed: number
  total_chunks: number
  errors: { video_id: string; error: string }[]
}

export interface IndexedVideosResponse {
  total_videos: number
  videos: {
    video_id: string
    title: string
    chunks: number
  }[]
}

export async function askQuestion(
  question: string,
  topK: number = 5
): Promise<AskResponse> {
  const { data } = await api.post("/rag/ask", { question, top_k: topK })
  return data
}

export async function semanticSearch(
  query: string,
  topK: number = 10
): Promise<SearchResult[]> {
  const { data } = await api.post("/rag/search", { query, top_k: topK })
  return data
}

export async function getIndexStats(): Promise<IndexStats> {
  const { data } = await api.get("/rag/stats")
  return data
}

export async function indexAllVideos(): Promise<IndexResult> {
  const { data } = await api.post("/rag/index/all")
  return data
}

export async function indexVideo(videoId: string): Promise<{
  video_id: string
  chunks_indexed: number
  message: string
}> {
  const { data } = await api.post(`/rag/index/${videoId}`)
  return data
}

export async function getIndexedVideos(): Promise<IndexedVideosResponse> {
  const { data } = await api.get("/rag/videos/indexed")
  return data
}

export async function clearIndex(): Promise<{ message: string }> {
  const { data } = await api.delete("/rag/index")
  return data
}
