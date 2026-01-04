import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Mic,
  Sparkles,
  Play,
  Square,
  CheckCircle2,
  XCircle,
  Clock,
  SkipForward,
  Loader2,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  FileX,
  Upload,
} from "lucide-react"
import {
  getBatchWhisperCandidates,
  getBatchCleanupCandidates,
  createBatchWhisperStream,
  createBatchCleanupStream,
  getVideoStatusSummary,
  getNoTranscriptCandidates,
  getUploadCandidates,
  createBatchUploadStream,
  type BatchCandidate,
  type BatchCandidatesResponse,
  type BatchProgressEvent,
  type VideoStatusSummary,
} from "@/lib/api"

type OperationType = "no-transcript" | "whisper" | "cleanup" | "upload"
type VideoStatus = "pending" | "processing" | "done" | "skipped" | "failed" | "excluded"

interface VideoItem extends BatchCandidate {
  selected: boolean
  status: VideoStatus
  message?: string
}

const ITEMS_PER_PAGE = 10

export default function BatchOperations() {
  const [operationType, setOperationType] = useState<OperationType>("no-transcript")
  const [loading, setLoading] = useState(true)
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [alreadyDone, setAlreadyDone] = useState<{ id: string; title: string }[]>([])
  const [summary, setSummary] = useState<BatchCandidatesResponse["summary"] | null>(null)
  const [statusSummary, setStatusSummary] = useState<VideoStatusSummary | null>(null)

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const totalPages = Math.ceil(videos.length / ITEMS_PER_PAGE)
  const paginatedVideos = videos.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  )

  // Batch execution state
  const [isRunning, setIsRunning] = useState(false)
  const [eventSource, setEventSource] = useState<EventSource | null>(null)
  const [progress, setProgress] = useState({ current: 0, total: 0, completed: 0, skipped: 0, failed: 0 })
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null)
  const [autoUpload, setAutoUpload] = useState(true)
  const [parallelWorkers, setParallelWorkers] = useState(2)

  const loadCandidates = useCallback(async () => {
    setLoading(true)
    try {
      const getCandidates = () => {
        switch (operationType) {
          case "no-transcript":
            return getNoTranscriptCandidates()
          case "whisper":
            return getBatchWhisperCandidates()
          case "cleanup":
            return getBatchCleanupCandidates()
          case "upload":
            return getUploadCandidates()
        }
      }
      const [data, statusData] = await Promise.all([
        getCandidates(),
        getVideoStatusSummary(),
      ])

      setVideos(data.candidates.map(c => ({ ...c, selected: true, status: "pending" as VideoStatus })))
      setAlreadyDone(data.already_done)
      setSummary(data.summary)
      setStatusSummary(statusData)
      setCurrentPage(1)
    } catch (err) {
      console.error("Failed to load candidates:", err)
    } finally {
      setLoading(false)
    }
  }, [operationType])

  useEffect(() => {
    loadCandidates()
  }, [loadCandidates])

  const selectedVideos = videos.filter(v => v.selected)
  const selectedCost = selectedVideos.reduce((sum, v) => sum + (v.estimated_cost || 0), 0)

  // Create a lookup map for video status details
  const videoStatusMap = new Map(
    statusSummary?.videos.map(v => [v.id, v]) || []
  )

  const toggleVideo = (id: string) => {
    setVideos(prev => prev.map(v =>
      v.id === id ? { ...v, selected: !v.selected } : v
    ))
  }

  const selectAll = () => {
    setVideos(prev => prev.map(v => ({ ...v, selected: true })))
  }

  const deselectAll = () => {
    setVideos(prev => prev.map(v => ({ ...v, selected: false })))
  }

  const startBatch = () => {
    const selectedIds = selectedVideos.map(v => v.id)
    if (selectedIds.length === 0) return

    setIsRunning(true)
    setProgress({ current: 0, total: selectedIds.length, completed: 0, skipped: 0, failed: 0 })

    // Reset video statuses
    setVideos(prev => prev.map(v => ({
      ...v,
      status: v.selected ? "pending" : "excluded",
      message: undefined,
    })))

    // Select the appropriate stream based on operation type
    let es: EventSource
    if (operationType === "cleanup") {
      es = createBatchCleanupStream(selectedIds, "fa", true, parallelWorkers)
    } else if (operationType === "upload") {
      es = createBatchUploadStream(selectedIds, "fa", parallelWorkers)
    } else {
      // no-transcript and whisper both use Whisper stream
      es = createBatchWhisperStream(selectedIds, "fa", autoUpload, parallelWorkers)
    }

    es.addEventListener("start", (e) => {
      const data = JSON.parse(e.data)
      setProgress(prev => ({ ...prev, total: data.total }))
    })

    es.addEventListener("progress", (e) => {
      const data: BatchProgressEvent = JSON.parse(e.data)
      setProgress({
        current: data.current,
        total: data.total,
        completed: data.completed,
        skipped: data.skipped,
        failed: data.failed,
      })
      setCurrentVideoId(data.video_id)

      // Update video status
      setVideos(prev => prev.map(v =>
        v.id === data.video_id
          ? { ...v, status: data.status, message: data.message }
          : v
      ))
    })

    es.addEventListener("complete", (e) => {
      const data = JSON.parse(e.data)
      setProgress({
        current: data.total,
        total: data.total,
        completed: data.completed,
        skipped: data.skipped,
        failed: data.failed,
      })
      setIsRunning(false)
      setCurrentVideoId(null)
      es.close()
      setEventSource(null)
    })

    es.addEventListener("error", (e) => {
      console.error("SSE error:", e)
      if (es.readyState === EventSource.CLOSED) {
        setIsRunning(false)
        setEventSource(null)
      }
    })

    setEventSource(es)
  }

  const cancelBatch = () => {
    if (eventSource) {
      eventSource.close()
      setEventSource(null)
    }
    setIsRunning(false)
    setCurrentVideoId(null)
  }

  const getStatusIcon = (status: VideoStatus) => {
    switch (status) {
      case "done":
        return <CheckCircle2 className="h-4 w-4 text-green-600" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-600" />
      case "skipped":
        return <SkipForward className="h-4 w-4 text-yellow-600" />
      case "processing":
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
      case "excluded":
        return <span className="h-4 w-4 text-gray-400">—</span>
      default:
        return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  const progressPercent = progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Batch Operations</h1>
              <p className="text-sm text-muted-foreground">
                Process multiple videos at once
              </p>
            </div>
            <Button variant="outline" onClick={() => window.history.back()}>
              Back to Library
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Operation Type Tabs */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant={operationType === "no-transcript" ? "default" : "outline"}
            onClick={() => setOperationType("no-transcript")}
            disabled={isRunning}
            className={operationType === "no-transcript" ? "bg-red-600 hover:bg-red-700" : ""}
          >
            <FileX className="h-4 w-4 mr-2" />
            No Transcript
          </Button>
          <Button
            variant={operationType === "whisper" ? "default" : "outline"}
            onClick={() => setOperationType("whisper")}
            disabled={isRunning}
          >
            <Mic className="h-4 w-4 mr-2" />
            Needs Whisper
          </Button>
          <Button
            variant={operationType === "cleanup" ? "default" : "outline"}
            onClick={() => setOperationType("cleanup")}
            disabled={isRunning}
          >
            <Sparkles className="h-4 w-4 mr-2" />
            Needs Cleanup
          </Button>
          <Button
            variant={operationType === "upload" ? "default" : "outline"}
            onClick={() => setOperationType("upload")}
            disabled={isRunning}
            className={operationType === "upload" ? "bg-green-600 hover:bg-green-700" : ""}
          >
            <Upload className="h-4 w-4 mr-2" />
            Needs YouTube Upload
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={loadCandidates}
            disabled={isRunning || loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        {/* Overall Video Status Summary */}
        {statusSummary && (
          <Card className="border-slate-200 dark:border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Overall Video Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 text-sm">
                <div className="text-center p-2 bg-slate-50 dark:bg-slate-800 rounded">
                  <div className="text-2xl font-bold">{statusSummary.summary.total_videos}</div>
                  <span className="text-muted-foreground text-xs">Total Videos</span>
                </div>
                <div className="text-center p-2 bg-blue-50 dark:bg-blue-900/20 rounded">
                  <div className="text-2xl font-bold text-blue-600">{statusSummary.summary.with_youtube_subtitle}</div>
                  <span className="text-muted-foreground text-xs">YouTube Subs</span>
                </div>
                <div className="text-center p-2 bg-purple-50 dark:bg-purple-900/20 rounded">
                  <div className="text-2xl font-bold text-purple-600">{statusSummary.summary.with_whisper}</div>
                  <span className="text-muted-foreground text-xs">Whisper Done</span>
                </div>
                <div className="text-center p-2 bg-green-50 dark:bg-green-900/20 rounded">
                  <div className="text-2xl font-bold text-green-600">{statusSummary.summary.with_cleaned}</div>
                  <span className="text-muted-foreground text-xs">Cleaned</span>
                </div>
                <div className="text-center p-2 bg-red-50 dark:bg-red-900/20 rounded">
                  <div className="text-2xl font-bold text-red-600">{statusSummary.summary.no_transcript}</div>
                  <span className="text-muted-foreground text-xs">No Transcript</span>
                </div>
                <div className="text-center p-2 bg-orange-50 dark:bg-orange-900/20 rounded">
                  <div className="text-2xl font-bold text-orange-600">{statusSummary.summary.needs_whisper}</div>
                  <span className="text-muted-foreground text-xs">Needs Whisper</span>
                </div>
                <div className="text-center p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded">
                  <div className="text-2xl font-bold text-yellow-600">{statusSummary.summary.needs_cleanup}</div>
                  <span className="text-muted-foreground text-xs">Needs Cleanup</span>
                </div>
                <div className="text-center p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded">
                  <div className="text-2xl font-bold text-emerald-600">{statusSummary.summary.fully_processed}</div>
                  <span className="text-muted-foreground text-xs">Fully Done</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Operation Summary Card */}
        {summary && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">
                {operationType === "no-transcript" ? "No Transcript" :
                 operationType === "whisper" ? "Needs Whisper" :
                 operationType === "cleanup" ? "Needs Cleanup" :
                 "Needs YouTube Upload"} - Batch
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Need processing:</span>
                  <div className="text-xl font-bold">{summary.total_candidates}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Already done:</span>
                  <div className="text-xl font-bold text-green-600">{summary.already_done}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Selected:</span>
                  <div className="text-xl font-bold text-blue-600">{selectedVideos.length}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Est. cost:</span>
                  <div className="text-xl font-bold">${selectedCost.toFixed(3)}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Progress Bar (when running) */}
        {isRunning && (
          <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
            <CardContent className="py-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    Processing: {progress.current}/{progress.total}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {progressPercent}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3 dark:bg-gray-700">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="flex gap-4 text-sm">
                  <span className="text-green-600">✓ {progress.completed} done</span>
                  <span className="text-yellow-600">⏭ {progress.skipped} skipped</span>
                  <span className="text-red-600">✗ {progress.failed} failed</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        <div className="flex items-center gap-4">
          {!isRunning ? (
            <>
              <Button onClick={startBatch} disabled={selectedVideos.length === 0}>
                <Play className="h-4 w-4 mr-2" />
                Start Batch ({selectedVideos.length} videos)
              </Button>
              <Button variant="outline" onClick={selectAll} disabled={loading}>
                Select All
              </Button>
              <Button variant="outline" onClick={deselectAll} disabled={loading}>
                Deselect All
              </Button>
              {/* Auto-upload toggle (only for Whisper operations) */}
              {(operationType === "no-transcript" || operationType === "whisper") && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoUpload}
                    onChange={(e) => setAutoUpload(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span>Auto-upload to YouTube</span>
                </label>
              )}
              {/* Parallel workers selector */}
              <label className="flex items-center gap-2 text-sm">
                <span>Parallel:</span>
                <select
                  value={parallelWorkers}
                  onChange={(e) => setParallelWorkers(Number(e.target.value))}
                  className="h-8 px-2 rounded border border-gray-300 bg-background text-sm"
                >
                  <option value={1}>1 (Sequential)</option>
                  <option value={2}>2 workers</option>
                  <option value={3}>3 workers</option>
                  <option value={4}>4 workers</option>
                </select>
              </label>
            </>
          ) : (
            <Button variant="destructive" onClick={cancelBatch}>
              <Square className="h-4 w-4 mr-2" />
              Cancel
            </Button>
          )}
        </div>

        {/* Video List */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">
                Videos to Process ({videos.length})
              </CardTitle>
              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                Loading candidates...
              </div>
            ) : videos.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {operationType === "no-transcript"
                  ? "All videos have at least one transcript. All done!"
                  : operationType === "whisper"
                  ? "All videos have Whisper transcripts. All done!"
                  : operationType === "cleanup"
                  ? "All videos have been cleaned. All done!"
                  : "All transcripts have been uploaded to YouTube. All done!"}
              </div>
            ) : (
              <div className="space-y-2">
                {paginatedVideos.map((video) => (
                  <div
                    key={video.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border ${
                      video.id === currentVideoId
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-950/20"
                        : video.status === "done"
                        ? "border-green-200 bg-green-50 dark:bg-green-950/20"
                        : video.status === "failed"
                        ? "border-red-200 bg-red-50 dark:bg-red-950/20"
                        : ""
                    }`}
                  >
                    {/* Checkbox */}
                    <input
                      type="checkbox"
                      checked={video.selected}
                      onChange={() => toggleVideo(video.id)}
                      disabled={isRunning}
                      className="h-4 w-4 rounded border-gray-300"
                    />

                    {/* Status Icon */}
                    <div className="w-6">{getStatusIcon(video.status)}</div>

                    {/* Video Info */}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{video.title}</div>
                      <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-2 mt-1">
                        {video.duration_seconds && (
                          <span>{Math.round(video.duration_seconds / 60)} min</span>
                        )}
                        {video.estimated_cost !== undefined && (
                          <span className="text-orange-600">${video.estimated_cost.toFixed(3)}</span>
                        )}
                        {/* Video Status Badges */}
                        {(() => {
                          const status = videoStatusMap.get(video.id)
                          if (!status) return null
                          return (
                            <>
                              {status.has_youtube && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-blue-50 text-blue-700 border-blue-200">
                                  YT Sub
                                </Badge>
                              )}
                              {status.has_whisper && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-purple-50 text-purple-700 border-purple-200">
                                  Whisper
                                </Badge>
                              )}
                              {status.has_cleaned && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-green-50 text-green-700 border-green-200">
                                  Cleaned
                                </Badge>
                              )}
                              {status.uploaded_to_yt && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-emerald-50 text-emerald-700 border-emerald-200">
                                  Uploaded
                                </Badge>
                              )}
                              {!status.has_youtube && !status.has_whisper && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-red-50 text-red-700 border-red-200">
                                  No Transcript
                                </Badge>
                              )}
                            </>
                          )
                        })()}
                        {video.source && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            src: {video.source}
                          </Badge>
                        )}
                      </div>
                      {video.message && (
                        <div className="text-xs mt-1 text-muted-foreground">
                          {video.message}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Already Done Section */}
        {alreadyDone.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                Already Processed ({alreadyDone.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground space-y-1 max-h-40 overflow-auto">
                {alreadyDone.map((v) => (
                  <div key={v.id} className="truncate">
                    {v.title}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}
