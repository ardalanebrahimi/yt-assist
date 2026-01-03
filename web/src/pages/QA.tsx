import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Send,
  Loader2,
  Database,
  RefreshCw,
  ExternalLink,
  MessageSquare,
  Search,
  Trash2,
  ChevronLeft,
  Info,
} from "lucide-react"
import {
  askQuestion,
  getIndexStats,
  indexAllVideos,
  getIndexedVideos,
  clearIndex,
  type AskResponse,
  type IndexStats,
  type IndexedVideosResponse,
} from "@/lib/api"

interface Message {
  id: string
  type: "user" | "assistant"
  content: string
  sources?: AskResponse["sources"]
  chunksUsed?: number
  timestamp: Date
}

export default function QA() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [indexStats, setIndexStats] = useState<IndexStats | null>(null)
  const [indexedVideos, setIndexedVideos] = useState<IndexedVideosResponse | null>(null)
  const [indexing, setIndexing] = useState(false)
  const [showIndex, setShowIndex] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    loadIndexStats()
  }, [])

  const loadIndexStats = async () => {
    try {
      const [stats, videos] = await Promise.all([
        getIndexStats(),
        getIndexedVideos(),
      ])
      setIndexStats(stats)
      setIndexedVideos(videos)
    } catch (err) {
      console.error("Failed to load index stats:", err)
    }
  }

  const handleIndexAll = async () => {
    setIndexing(true)
    try {
      const result = await indexAllVideos()
      alert(`Indexed ${result.videos_processed} videos with ${result.total_chunks} chunks.${
        result.errors.length > 0 ? `\n${result.errors.length} errors occurred.` : ""
      }`)
      await loadIndexStats()
    } catch (err: any) {
      alert(`Indexing failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setIndexing(false)
    }
  }

  const handleClearIndex = async () => {
    if (!confirm("Are you sure you want to clear the entire index? You will need to re-index all videos.")) {
      return
    }
    try {
      await clearIndex()
      await loadIndexStats()
      alert("Index cleared successfully.")
    } catch (err: any) {
      alert(`Failed to clear index: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setLoading(true)

    try {
      const response = await askQuestion(userMessage.content)

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: response.answer,
        sources: response.sources,
        chunksUsed: response.chunks_used,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: `Error: ${err.response?.data?.detail || err.message || "Failed to get response"}`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => (window.location.hash = "")}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <MessageSquare className="h-6 w-6" />
                  Ask Your Videos
                </h1>
                <p className="text-sm text-muted-foreground">
                  RAG-powered Q&A about your video content
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowIndex(!showIndex)}
              >
                <Database className="h-4 w-4 mr-2" />
                Index
                {indexStats && (
                  <Badge variant="secondary" className="ml-2">
                    {indexStats.videos_indexed} videos
                  </Badge>
                )}
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Index Panel (collapsible) */}
        {showIndex && (
          <div className="w-80 border-r bg-card overflow-y-auto">
            <div className="p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Index Management</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={loadIndexStats}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>

              {/* Stats */}
              {indexStats && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Statistics</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Videos:</span>
                      <span className="font-medium">{indexStats.videos_indexed}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Chunks:</span>
                      <span className="font-medium">{indexStats.total_chunks}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model:</span>
                      <span className="font-medium text-xs">{indexStats.embedding_model}</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Actions */}
              <div className="space-y-2">
                <Button
                  className="w-full"
                  onClick={handleIndexAll}
                  disabled={indexing}
                >
                  {indexing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Indexing...
                    </>
                  ) : (
                    <>
                      <Database className="h-4 w-4 mr-2" />
                      Index All Videos
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleClearIndex}
                  disabled={indexing}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Clear Index
                </Button>
              </div>

              {/* Indexed Videos */}
              {indexedVideos && indexedVideos.videos.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">
                    Indexed Videos ({indexedVideos.total_videos})
                  </h4>
                  <div className="space-y-1 max-h-64 overflow-y-auto">
                    {indexedVideos.videos.map((v) => (
                      <div
                        key={v.video_id}
                        className="text-xs p-2 rounded bg-muted/50 flex justify-between items-center"
                      >
                        <span className="truncate flex-1 mr-2" title={v.title}>
                          {v.title}
                        </span>
                        <Badge variant="secondary" className="shrink-0">
                          {v.chunks}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Info */}
              <div className="text-xs text-muted-foreground p-3 bg-muted/50 rounded">
                <Info className="h-3 w-3 inline mr-1" />
                Index all videos to enable Q&A. This uses OpenAI embeddings
                (~$0.0001 per 1K tokens).
              </div>
            </div>
          </div>
        )}

        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="flex-1 flex items-center justify-center h-full">
                <div className="text-center space-y-4 max-w-md">
                  <MessageSquare className="h-12 w-12 mx-auto text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Ask anything about your videos</h2>
                  <p className="text-muted-foreground">
                    Your questions will be answered based on your video transcripts.
                    The AI will cite which videos it used.
                  </p>
                  {indexStats && indexStats.videos_indexed === 0 && (
                    <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-yellow-800 dark:text-yellow-200 text-sm">
                      No videos indexed yet. Open the Index panel and click "Index All Videos" to get started.
                    </div>
                  )}
                  <div className="text-sm text-muted-foreground space-y-1">
                    <p>Example questions:</p>
                    <p className="italic">"What have I said about microservices?"</p>
                    <p className="italic">"Summarize my videos about AI agents"</p>
                    <p className="italic">"Which video talks about clean architecture?"</p>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-4 ${
                      message.type === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>

                    {/* Sources */}
                    {message.sources && message.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-border/50">
                        <p className="text-xs font-medium mb-2 opacity-70">
                          Sources ({message.chunksUsed} chunks used):
                        </p>
                        <div className="space-y-1">
                          {message.sources.map((source) => (
                            <a
                              key={source.video_id}
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-xs hover:underline opacity-80 hover:opacity-100"
                            >
                              <ExternalLink className="h-3 w-3" />
                              {source.title}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg p-4">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t bg-card p-4">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about your videos..."
                disabled={loading}
                className="flex-1"
              />
              <Button type="submit" disabled={loading || !input.trim()}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
