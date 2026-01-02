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
