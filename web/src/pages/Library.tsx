import { useState, useEffect } from "react"
import {
  RefreshCw,
  Download,
  Search,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  Play,
  Mic,
  Layers,
  MessageSquare,
  Sparkles,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  getVideos,
  getSyncStatus,
  syncAllVideos,
  getVideo,
  transcribeVideo,
  cleanupTranscript,
  uploadCleanedToYouTube,
  saveCleanedTranscript,
  authenticateYouTube,
  getYouTubeAuthStatus,
  listYouTubeCaptions,
  deleteYouTubeCaption,
  createDub,
  listDubs,
  type Video,
  type VideoDetail,
  type SyncStatus,
  type CleanupResponse,
} from "@/lib/api"
import { formatDuration, formatDate, formatNumber } from "@/lib/utils"
import { TranscriptManager } from "@/components/TranscriptManager"

export default function Library() {
  const [videos, setVideos] = useState<Video[]>([])
  const [total, setTotal] = useState(0)
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("")
  const [selectedVideo, setSelectedVideo] = useState<VideoDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [transcribing, setTranscribing] = useState<string | null>(null) // video ID being transcribed
  const [cleaning, setCleaning] = useState(false)
  const [cleanupResult, setCleanupResult] = useState<CleanupResponse | null>(null)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [ytAuthStatus, setYtAuthStatus] = useState<{ authenticated: boolean; message: string } | null>(null)
  const [authenticating, setAuthenticating] = useState(false)
  const [dubbing, setDubbing] = useState(false)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [videosRes, statusRes] = await Promise.all([
        getVideos({
          page: 1,
          page_size: 100,
          status: statusFilter || undefined,
          search: search || undefined,
        }),
        getSyncStatus(),
      ])
      setVideos(videosRes.items)
      setTotal(videosRes.total)
      setSyncStatus(statusRes)
    } catch (err) {
      setError("Failed to connect to API. Make sure the server is running.")
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [statusFilter, search])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await syncAllVideos()
      await fetchData()
    } catch (err) {
      setError("Sync failed. Please try again.")
      console.error(err)
    } finally {
      setSyncing(false)
    }
  }

  const handleVideoClick = async (video: Video) => {
    try {
      const detail = await getVideo(video.id)
      setSelectedVideo(detail)
    } catch (err) {
      console.error(err)
    }
  }

  const handleTranscribe = async (videoId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    setTranscribing(videoId)
    try {
      const result = await transcribeVideo(videoId, "fa")
      if (result.success) {
        // Refresh video data
        await fetchData()
        if (selectedVideo && selectedVideo.id === videoId) {
          const detail = await getVideo(videoId)
          setSelectedVideo(detail)
        }
        alert(`Transcription complete! Cost: ~$${result.cost_estimate?.toFixed(3) || "N/A"}`)
      } else {
        alert(`Transcription failed: ${result.message}`)
      }
    } catch (err) {
      console.error(err)
      alert("Transcription failed. Check console for details.")
    } finally {
      setTranscribing(null)
    }
  }

  const handleCleanup = async (videoId: string) => {
    setCleaning(true)
    setCleanupResult(null)
    try {
      const result = await cleanupTranscript(videoId, "fa", true)
      if (result.success) {
        setCleanupResult(result)
      } else {
        alert(`Cleanup failed: ${result.message}`)
      }
    } catch (err) {
      console.error(err)
      alert("Cleanup failed. Check console for details.")
    } finally {
      setCleaning(false)
    }
  }

  const handleUploadToYouTube = async (videoId: string, content: string) => {
    setUploading(true)
    try {
      const result = await uploadCleanedToYouTube(videoId, content, "fa", false)
      if (result.success) {
        alert("Successfully uploaded to YouTube!")
        setCleanupResult(null)
      } else {
        alert(`Upload failed: ${result.message}`)
      }
    } catch (err: any) {
      console.error(err)
      alert(`Upload failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleSaveCleaned = async (videoId: string, content: string) => {
    setSaving(true)
    try {
      const result = await saveCleanedTranscript(videoId, content, "fa")
      if (result.success) {
        alert("Cleaned transcript saved!")
        // Refresh video data
        const detail = await getVideo(videoId)
        setSelectedVideo(detail)
        setCleanupResult(null)
      } else {
        alert(`Save failed: ${result.message}`)
      }
    } catch (err: any) {
      console.error(err)
      alert(`Save failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const checkYouTubeAuth = async () => {
    try {
      const status = await getYouTubeAuthStatus()
      setYtAuthStatus(status)
    } catch (err) {
      console.error(err)
    }
  }

  const handleYouTubeAuth = async () => {
    setAuthenticating(true)
    try {
      const result = await authenticateYouTube()
      if (result.success) {
        alert("YouTube authentication successful!")
        await checkYouTubeAuth()
      } else {
        alert(`Authentication failed: ${result.message}`)
      }
    } catch (err: any) {
      console.error(err)
      alert(`Authentication failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setAuthenticating(false)
    }
  }

  const handleCreateDub = async (videoId: string, targetLanguage: string, voice: string) => {
    setDubbing(true)
    try {
      const result = await createDub(videoId, {
        source_language: "fa",
        target_language: targetLanguage,
        voice: voice,
      })
      if (result.success) {
        alert(`Dub created successfully! ${result.segments_count} segments, ${result.duration_seconds?.toFixed(0)}s duration`)
      } else {
        alert(`Dubbing failed: ${result.message}`)
      }
    } catch (err: any) {
      console.error(err)
      alert(`Dubbing failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setDubbing(false)
    }
  }

  // Check YouTube auth status on modal open
  useEffect(() => {
    if (selectedVideo) {
      checkYouTubeAuth()
    }
  }, [selectedVideo])

  const getStatusBadge = (video: Video) => {
    if (video.sync_status === "synced") {
      return video.has_transcript ? (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3" /> Synced
        </Badge>
      ) : (
        <Badge variant="warning" className="gap-1">
          <FileText className="h-3 w-3" /> No Transcript
        </Badge>
      )
    }
    if (video.sync_status === "error") {
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" /> Error
        </Badge>
      )
    }
    return (
      <Badge variant="secondary" className="gap-1">
        <Clock className="h-3 w-3" /> Pending
      </Badge>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background p-8">
        <Card className="max-w-lg mx-auto">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <XCircle className="h-12 w-12 text-destructive mx-auto" />
              <h2 className="text-xl font-semibold">Connection Error</h2>
              <p className="text-muted-foreground">{error}</p>
              <code className="block bg-muted p-2 rounded text-sm">
                uvicorn app.main:app --reload
              </code>
              <Button onClick={fetchData}>Retry</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">YT-Assist</h1>
              <p className="text-sm text-muted-foreground">Video Library</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => window.location.hash = "studio"}
              >
                <Sparkles className="h-4 w-4 mr-2" />
                Content Studio
              </Button>
              <Button
                variant="outline"
                onClick={() => window.location.hash = "qa"}
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                Ask Videos
              </Button>
              <Button
                variant="outline"
                onClick={() => window.location.hash = "batch"}
              >
                <Layers className="h-4 w-4 mr-2" />
                Batch Operations
              </Button>
              <Button
                variant="outline"
                onClick={() => window.open("http://127.0.0.1:8000/api/export/jsonl")}
              >
                <Download className="h-4 w-4 mr-2" />
                Export JSONL
              </Button>
              <Button onClick={handleSync} disabled={syncing}>
                <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? "animate-spin" : ""}`} />
                {syncing ? "Syncing..." : "Sync All"}
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Stats Cards */}
        {syncStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Videos
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{syncStatus.total_videos}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Synced</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{syncStatus.synced}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Pending</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-yellow-600">{syncStatus.pending}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Errors</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{syncStatus.errors}</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search videos..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant={statusFilter === "" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("")}
            >
              All
            </Button>
            <Button
              variant={statusFilter === "synced" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("synced")}
            >
              Synced
            </Button>
            <Button
              variant={statusFilter === "pending" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("pending")}
            >
              Pending
            </Button>
            <Button
              variant={statusFilter === "error" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("error")}
            >
              Errors
            </Button>
          </div>
        </div>

        {/* Video List */}
        <div className="grid gap-4">
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">Loading...</div>
          ) : videos.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground mb-4">No videos found</p>
                <Button onClick={handleSync}>Sync from YouTube</Button>
              </CardContent>
            </Card>
          ) : (
            videos.map((video) => (
              <Card
                key={video.id}
                className="hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => handleVideoClick(video)}
              >
                <CardContent className="p-4">
                  <div className="flex gap-4">
                    {/* Thumbnail */}
                    <div className="relative flex-shrink-0 w-40 h-24 bg-muted rounded-md overflow-hidden">
                      {video.thumbnail_url ? (
                        <img
                          src={video.thumbnail_url}
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Play className="h-8 w-8 text-muted-foreground" />
                        </div>
                      )}
                      <div className="absolute bottom-1 right-1 bg-black/80 text-white text-xs px-1 rounded">
                        {formatDuration(video.duration_seconds)}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-medium line-clamp-2">{video.title}</h3>
                        {getStatusBadge(video)}
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                        <span>{formatDate(video.published_at)}</span>
                        {video.view_count && <span>{formatNumber(video.view_count)} views</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <a
                          href={`https://youtube.com/watch?v=${video.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Watch on YouTube
                        </a>
                        {video.sync_status === "synced" && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-xs"
                            onClick={(e) => handleTranscribe(video.id, e)}
                            disabled={transcribing === video.id}
                          >
                            <Mic className={`h-3 w-3 mr-1 ${transcribing === video.id ? "animate-pulse" : ""}`} />
                            {transcribing === video.id ? "Transcribing..." : "Whisper"}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Video count */}
        {!loading && videos.length > 0 && (
          <p className="text-sm text-muted-foreground mt-4 text-center">
            Showing {videos.length} of {total} videos
          </p>
        )}
      </main>

      {/* Video Detail Modal */}
      {selectedVideo && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
          onClick={() => {
            setSelectedVideo(null)
            setCleanupResult(null)
          }}
        >
          <Card className="max-w-2xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <CardTitle className="text-lg">{selectedVideo.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Published:</span>{" "}
                  {formatDate(selectedVideo.published_at)}
                </div>
                <div>
                  <span className="text-muted-foreground">Duration:</span>{" "}
                  {formatDuration(selectedVideo.duration_seconds)}
                </div>
                <div>
                  <span className="text-muted-foreground">Views:</span>{" "}
                  {formatNumber(selectedVideo.view_count)}
                </div>
                <div>
                  <span className="text-muted-foreground">Video ID:</span>{" "}
                  <code className="bg-muted px-1 rounded">{selectedVideo.id}</code>
                </div>
              </div>

              {selectedVideo.tags && selectedVideo.tags.length > 0 && (
                <div>
                  <span className="text-sm text-muted-foreground">Tags:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedVideo.tags.slice(0, 10).map((tag) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* YouTube Auth Status */}
              {ytAuthStatus && !ytAuthStatus.authenticated && (
                <div className="flex items-center gap-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md">
                  <span className="text-sm text-yellow-800 dark:text-yellow-200">
                    YouTube not authenticated
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleYouTubeAuth}
                    disabled={authenticating}
                  >
                    {authenticating ? "Authenticating..." : "Authenticate YouTube"}
                  </Button>
                </div>
              )}

              {/* Transcript Manager */}
              <TranscriptManager
                videoId={selectedVideo.id}
                transcripts={selectedVideo.transcripts || []}
                onCleanup={() => handleCleanup(selectedVideo.id)}
                onTranscribe={() => handleTranscribe(selectedVideo.id)}
                onUploadToYouTube={(content) => handleUploadToYouTube(selectedVideo.id, content)}
                onSaveTranscript={(content) => handleSaveCleaned(selectedVideo.id, content)}
                isTranscribing={transcribing === selectedVideo.id}
                isCleaning={cleaning}
                isUploading={uploading}
                isSaving={saving}
                cleanupResult={cleanupResult && cleanupResult.original && cleanupResult.cleaned ? {
                  original: cleanupResult.original,
                  cleaned: cleanupResult.cleaned,
                  changes_summary: cleanupResult.changes_summary,
                } : null}
                onCleanupDiscard={() => setCleanupResult(null)}
                durationSeconds={selectedVideo.duration_seconds || 0}
                fetchYouTubeCaptions={() => listYouTubeCaptions(selectedVideo.id)}
                deleteYouTubeCaption={(captionId) => deleteYouTubeCaption(selectedVideo.id, captionId)}
                onCreateDub={(targetLanguage, voice) => handleCreateDub(selectedVideo.id, targetLanguage, voice)}
                fetchDubs={() => listDubs(selectedVideo.id)}
                isDubbing={dubbing}
              />

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => {
                  setSelectedVideo(null)
                  setCleanupResult(null)
                }}>
                  Close
                </Button>
                <Button
                  onClick={() =>
                    window.open(`https://youtube.com/watch?v=${selectedVideo.id}`, "_blank")
                  }
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open on YouTube
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
