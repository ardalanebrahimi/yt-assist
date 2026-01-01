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
  type Video,
  type VideoDetail,
  type SyncStatus,
} from "@/lib/api"
import { formatDuration, formatDate, formatNumber } from "@/lib/utils"

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
          onClick={() => setSelectedVideo(null)}
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

              {selectedVideo.transcripts && selectedVideo.transcripts.length > 0 ? (
                <div>
                  <h4 className="font-medium mb-2">Transcript</h4>
                  <div className="bg-muted rounded-md p-3 max-h-60 overflow-auto text-sm">
                    {selectedVideo.transcripts[0].clean_content.substring(0, 2000)}
                    {selectedVideo.transcripts[0].clean_content.length > 2000 && "..."}
                  </div>
                </div>
              ) : (
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md p-3 text-sm">
                  No transcript available for this video
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setSelectedVideo(null)}>
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
