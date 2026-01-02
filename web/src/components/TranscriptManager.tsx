import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Mic,
  Sparkles,
  Youtube,
  Upload,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  GitCompare,
  Eye,
  Check,
} from "lucide-react"
import { TranscriptDiff } from "./TranscriptDiff"
import type { Transcript } from "@/lib/api"

interface YouTubeCaption {
  id: string
  language: string
  name: string
  is_auto_synced: boolean
  is_draft: boolean
  track_kind: string
}

interface TranscriptManagerProps {
  videoId: string
  transcripts: Transcript[]
  onCleanup: () => void
  onTranscribe: () => void
  onUploadToYouTube: (content: string) => void
  onSaveTranscript: (content: string) => void
  isTranscribing: boolean
  isCleaning: boolean
  isUploading: boolean
  isSaving: boolean
  cleanupResult: { original: string; cleaned: string; changes_summary?: string } | null
  onCleanupDiscard: () => void
  durationSeconds: number
  // YouTube caption functions
  fetchYouTubeCaptions: () => Promise<YouTubeCaption[]>
  deleteYouTubeCaption: (captionId: string) => Promise<boolean>
}

const sourceIcons: Record<string, React.ReactNode> = {
  youtube: <Youtube className="h-4 w-4" />,
  whisper: <Mic className="h-4 w-4" />,
  cleaned: <Sparkles className="h-4 w-4" />,
}

const sourceColors: Record<string, string> = {
  youtube: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200",
  whisper: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200",
  cleaned: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-200",
}

export function TranscriptManager({
  videoId,
  transcripts,
  onCleanup,
  onTranscribe,
  onUploadToYouTube,
  onSaveTranscript,
  isTranscribing,
  isCleaning,
  isUploading,
  isSaving,
  cleanupResult,
  onCleanupDiscard,
  durationSeconds,
  fetchYouTubeCaptions,
  deleteYouTubeCaption,
}: TranscriptManagerProps) {
  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null)
  const [compareWith, setCompareWith] = useState<Transcript | null>(null)
  const [showCompare, setShowCompare] = useState(false)
  const [youtubeCaptions, setYoutubeCaptions] = useState<YouTubeCaption[]>([])
  const [loadingCaptions, setLoadingCaptions] = useState(false)
  const [deletingCaption, setDeletingCaption] = useState<string | null>(null)
  const [showYoutubeCaptions, setShowYoutubeCaptions] = useState(false)
  const [expandedTranscript, setExpandedTranscript] = useState<number | null>(null)

  // Sort transcripts: cleaned first, then whisper, then youtube
  const sortedTranscripts = [...transcripts].sort((a, b) => {
    const priority: Record<string, number> = { cleaned: 0, whisper: 1, youtube: 2 }
    return (priority[a.source] ?? 3) - (priority[b.source] ?? 3)
  })

  // Set initial selected transcript
  useEffect(() => {
    if (sortedTranscripts.length > 0 && !selectedTranscript) {
      setSelectedTranscript(sortedTranscripts[0])
    }
  }, [sortedTranscripts])

  const loadYouTubeCaptions = async () => {
    setLoadingCaptions(true)
    try {
      const captions = await fetchYouTubeCaptions()
      setYoutubeCaptions(captions)
    } catch (err) {
      console.error("Failed to load YouTube captions:", err)
    } finally {
      setLoadingCaptions(false)
    }
  }

  const handleDeleteCaption = async (captionId: string) => {
    setDeletingCaption(captionId)
    try {
      const success = await deleteYouTubeCaption(captionId)
      if (success) {
        setYoutubeCaptions(prev => prev.filter(c => c.id !== captionId))
      }
    } catch (err) {
      console.error("Failed to delete caption:", err)
    } finally {
      setDeletingCaption(null)
    }
  }

  // If cleanup result is available, show the diff view
  if (cleanupResult) {
    return (
      <TranscriptDiff
        original={cleanupResult.original}
        cleaned={cleanupResult.cleaned}
        changesSummary={cleanupResult.changes_summary}
        onAccept={onSaveTranscript}
        onReject={onCleanupDiscard}
        onUploadToYouTube={onUploadToYouTube}
        onSave={onSaveTranscript}
        isUploading={isUploading}
        isSaving={isSaving}
      />
    )
  }

  // If comparing two transcripts
  if (showCompare && selectedTranscript && compareWith) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="font-medium">
            Comparing: {selectedTranscript.source} vs {compareWith.source}
          </h4>
          <Button variant="outline" size="sm" onClick={() => setShowCompare(false)}>
            Back to list
          </Button>
        </div>
        <TranscriptDiff
          original={selectedTranscript.raw_content}
          cleaned={compareWith.raw_content}
          onAccept={() => {}}
          onReject={() => setShowCompare(false)}
          onUploadToYouTube={() => onUploadToYouTube(compareWith.raw_content)}
          onSave={() => {}}
          isUploading={isUploading}
          isSaving={false}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Transcript Versions Section */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium">Transcript Versions ({sortedTranscripts.length})</h4>
          <div className="flex gap-2">
            {!sortedTranscripts.some(t => t.source === "whisper") && (
              <Button
                variant="outline"
                size="sm"
                onClick={onTranscribe}
                disabled={isTranscribing}
              >
                <Mic className={`h-4 w-4 mr-1 ${isTranscribing ? "animate-pulse" : ""}`} />
                {isTranscribing ? "Transcribing..." : "Whisper"}
                <span className="text-xs text-muted-foreground ml-1">
                  ~${((durationSeconds || 0) / 60 * 0.006).toFixed(3)}
                </span>
              </Button>
            )}
            {sortedTranscripts.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={onCleanup}
                disabled={isCleaning}
              >
                <Sparkles className={`h-4 w-4 mr-1 ${isCleaning ? "animate-pulse" : ""}`} />
                {isCleaning ? "Cleaning..." : "Clean with GPT"}
              </Button>
            )}
          </div>
        </div>

        {sortedTranscripts.length === 0 ? (
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md p-4">
            <p className="text-sm">No transcript available for this video</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sortedTranscripts.map((transcript, idx) => (
              <div
                key={transcript.id}
                className={`border rounded-md ${
                  selectedTranscript?.id === transcript.id
                    ? "border-primary ring-1 ring-primary"
                    : ""
                }`}
              >
                {/* Header */}
                <div
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50"
                  onClick={() => {
                    setSelectedTranscript(transcript)
                    setExpandedTranscript(expandedTranscript === transcript.id ? null : transcript.id)
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Badge className={`${sourceColors[transcript.source]} gap-1`}>
                      {sourceIcons[transcript.source]}
                      {transcript.source}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      ({transcript.language_code})
                    </span>
                    {transcript.is_auto_generated && (
                      <span className="text-xs text-muted-foreground">auto</span>
                    )}
                    {selectedTranscript?.id === transcript.id && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {sortedTranscripts.length > 1 && selectedTranscript?.id !== transcript.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setCompareWith(transcript)
                          setShowCompare(true)
                        }}
                        title="Compare with selected"
                      >
                        <GitCompare className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onUploadToYouTube(transcript.raw_content)
                      }}
                      disabled={isUploading}
                      title="Upload to YouTube"
                    >
                      <Upload className="h-4 w-4" />
                    </Button>
                    {expandedTranscript === transcript.id ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </div>

                {/* Expanded content */}
                {expandedTranscript === transcript.id && (
                  <div className="border-t p-3">
                    <div className="bg-muted rounded-md p-3 max-h-64 overflow-auto text-sm whitespace-pre-wrap font-mono">
                      {transcript.raw_content}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* YouTube Captions Section */}
      <div className="border-t pt-4">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => {
            if (!showYoutubeCaptions) {
              loadYouTubeCaptions()
            }
            setShowYoutubeCaptions(!showYoutubeCaptions)
          }}
        >
          <h4 className="font-medium flex items-center gap-2">
            <Youtube className="h-4 w-4 text-red-600" />
            YouTube Captions
          </h4>
          <div className="flex items-center gap-2">
            {showYoutubeCaptions && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  loadYouTubeCaptions()
                }}
                disabled={loadingCaptions}
              >
                <RefreshCw className={`h-4 w-4 ${loadingCaptions ? "animate-spin" : ""}`} />
              </Button>
            )}
            {showYoutubeCaptions ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </div>

        {showYoutubeCaptions && (
          <div className="mt-3 space-y-2">
            {loadingCaptions ? (
              <div className="text-sm text-muted-foreground text-center py-4">
                Loading captions...
              </div>
            ) : youtubeCaptions.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-4 bg-muted/50 rounded-md">
                No captions uploaded to YouTube yet
              </div>
            ) : (
              youtubeCaptions.map((caption) => (
                <div
                  key={caption.id}
                  className="flex items-center justify-between p-3 border rounded-md"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{caption.language}</Badge>
                    <span className="text-sm">{caption.name}</span>
                    {caption.is_draft && (
                      <Badge variant="secondary" className="text-xs">Draft</Badge>
                    )}
                    {caption.is_auto_synced && (
                      <Badge variant="secondary" className="text-xs">Auto-synced</Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteCaption(caption.id)}
                    disabled={deletingCaption === caption.id}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    {deletingCaption === caption.id ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
