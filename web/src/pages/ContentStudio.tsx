import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  checkOverlap,
  generateOutline,
  generateScript,
  getSeriesSuggestions,
  getClipCandidates,
  type OverlapCheckResponse,
  type OutlineResponse,
  type ScriptResponse,
  type SeriesSuggestionResponse,
  type ClipCandidatesResponse,
} from "@/lib/api"
import {
  Lightbulb,
  FileText,
  Scissors,
  ListChecks,
  Sparkles,
  ArrowRight,
  Copy,
  Check,
  AlertCircle,
  Video,
  Clock,
  Target,
  ChevronDown,
  ChevronRight,
  Loader2,
} from "lucide-react"

type WizardStep = "idea" | "overlap" | "outline" | "script"

export default function ContentStudio() {
  const [activeTab, setActiveTab] = useState("wizard")

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => (window.location.hash = "")}
            >
              &larr; Library
            </Button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Sparkles className="h-6 w-6 text-purple-500" />
                Content Studio
              </h1>
              <p className="text-sm text-gray-500">AI-powered content creation tools</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => (window.location.hash = "qa")}>
              Q&A Chat
            </Button>
            <Button variant="outline" onClick={() => (window.location.hash = "batch")}>
              Batch Ops
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="wizard" className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4" />
              Video Wizard
            </TabsTrigger>
            <TabsTrigger value="series" className="flex items-center gap-2">
              <ListChecks className="h-4 w-4" />
              Series Planner
            </TabsTrigger>
            <TabsTrigger value="clips" className="flex items-center gap-2">
              <Scissors className="h-4 w-4" />
              Clip Finder
            </TabsTrigger>
          </TabsList>

          <TabsContent value="wizard">
            <VideoWizard />
          </TabsContent>

          <TabsContent value="series">
            <SeriesPlanner />
          </TabsContent>

          <TabsContent value="clips">
            <ClipFinder />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

function VideoWizard() {
  const [step, setStep] = useState<WizardStep>("idea")
  const [topic, setTopic] = useState("")
  const [loading, setLoading] = useState(false)
  const [overlap, setOverlap] = useState<OverlapCheckResponse | null>(null)
  const [selectedAngle, setSelectedAngle] = useState<string>("")
  const [outline, setOutline] = useState<OutlineResponse | null>(null)
  const [script, setScript] = useState<ScriptResponse | null>(null)
  const [targetDuration, setTargetDuration] = useState("10-15 minutes")
  const [copied, setCopied] = useState(false)

  const handleCheckOverlap = async () => {
    if (!topic.trim()) return
    setLoading(true)
    try {
      const result = await checkOverlap(topic)
      setOverlap(result)
      setStep("overlap")
      if (result.unique_angles.length > 0) {
        setSelectedAngle(result.unique_angles[0])
      }
    } catch (error) {
      console.error("Error checking overlap:", error)
    }
    setLoading(false)
  }

  const handleGenerateOutline = async () => {
    setLoading(true)
    try {
      const result = await generateOutline(topic, {
        angle: selectedAngle,
        target_duration: targetDuration,
      })
      setOutline(result)
      setStep("outline")
    } catch (error) {
      console.error("Error generating outline:", error)
    }
    setLoading(false)
  }

  const handleGenerateScript = async () => {
    if (!outline) return
    setLoading(true)
    try {
      const result = await generateScript(outline)
      setScript(result)
      setStep("script")
    } catch (error) {
      console.error("Error generating script:", error)
    }
    setLoading(false)
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const resetWizard = () => {
    setStep("idea")
    setTopic("")
    setOverlap(null)
    setSelectedAngle("")
    setOutline(null)
    setScript(null)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress Steps */}
      <div className="flex items-center justify-center gap-2 mb-8">
        {["idea", "overlap", "outline", "script"].map((s, i) => (
          <div key={s} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === s
                  ? "bg-purple-600 text-white"
                  : ["idea", "overlap", "outline", "script"].indexOf(step) > i
                  ? "bg-green-500 text-white"
                  : "bg-gray-200 text-gray-500"
              }`}
            >
              {i + 1}
            </div>
            {i < 3 && (
              <div
                className={`w-12 h-1 ${
                  ["idea", "overlap", "outline", "script"].indexOf(step) > i
                    ? "bg-green-500"
                    : "bg-gray-200"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Idea Input */}
      {step === "idea" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-yellow-500" />
              What's your video idea?
            </CardTitle>
            <CardDescription>
              Enter a topic, question, or concept you want to create a video about
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="e.g., How to optimize your LinkedIn profile for job hunting in Germany"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="min-h-[100px]"
            />
            <div className="flex items-center gap-4">
              <Select value={targetDuration} onValueChange={setTargetDuration}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Target duration" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5-7 minutes">5-7 minutes (Short)</SelectItem>
                  <SelectItem value="10-15 minutes">10-15 minutes (Standard)</SelectItem>
                  <SelectItem value="20-30 minutes">20-30 minutes (Deep dive)</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={handleCheckOverlap}
                disabled={!topic.trim() || loading}
                className="flex-1"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <ArrowRight className="h-4 w-4 mr-2" />
                )}
                Check & Continue
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Overlap Check */}
      {step === "overlap" && overlap && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-blue-500" />
                Content Overlap Analysis
              </CardTitle>
              <CardDescription>{overlap.summary}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Overlap Score */}
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-medium">Overlap Score</span>
                    <span className="text-sm text-gray-500">
                      {Math.round(overlap.overlap_score * 100)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${
                        overlap.overlap_score > 0.7
                          ? "bg-red-500"
                          : overlap.overlap_score > 0.3
                          ? "bg-yellow-500"
                          : "bg-green-500"
                      }`}
                      style={{ width: `${overlap.overlap_score * 100}%` }}
                    />
                  </div>
                </div>
                <Badge
                  variant={
                    overlap.has_overlap ? "destructive" : "default"
                  }
                >
                  {overlap.has_overlap ? "Has Overlap" : "Low Overlap"}
                </Badge>
              </div>

              {/* Related Videos */}
              {overlap.related_videos.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">Related Videos</h4>
                  <div className="space-y-2">
                    {overlap.related_videos.slice(0, 3).map((v) => (
                      <div
                        key={v.video_id}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded"
                      >
                        <span className="text-sm truncate flex-1">{v.title}</span>
                        <Badge variant="outline">
                          {Math.round(v.relevance_score * 100)}% match
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Unique Angles */}
              <div>
                <h4 className="text-sm font-medium mb-2">Suggested Unique Angles</h4>
                <div className="space-y-2">
                  {overlap.unique_angles.map((angle, i) => (
                    <div
                      key={i}
                      className={`p-3 border rounded cursor-pointer transition-colors ${
                        selectedAngle === angle
                          ? "border-purple-500 bg-purple-50"
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                      onClick={() => setSelectedAngle(angle)}
                    >
                      <div className="flex items-start gap-2">
                        <div
                          className={`w-4 h-4 rounded-full border-2 mt-0.5 ${
                            selectedAngle === angle
                              ? "border-purple-500 bg-purple-500"
                              : "border-gray-300"
                          }`}
                        >
                          {selectedAngle === angle && (
                            <Check className="h-3 w-3 text-white" />
                          )}
                        </div>
                        <span className="text-sm">{angle}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-2 pt-4">
                <Button variant="outline" onClick={() => setStep("idea")}>
                  Back
                </Button>
                <Button
                  onClick={handleGenerateOutline}
                  disabled={loading}
                  className="flex-1"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <FileText className="h-4 w-4 mr-2" />
                  )}
                  Generate Outline
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Step 3: Outline */}
      {step === "outline" && outline && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-green-500" />
                Video Outline
              </CardTitle>
              <CardDescription>
                Review and customize your video structure
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Title */}
              <div>
                <label className="text-sm font-medium">Title</label>
                <Input value={outline.title} readOnly className="mt-1" />
              </div>

              {/* Hook */}
              <div>
                <label className="text-sm font-medium">Opening Hook</label>
                <Textarea value={outline.hook} readOnly className="mt-1" />
              </div>

              {/* Sections */}
              <div>
                <label className="text-sm font-medium">Sections</label>
                <div className="mt-2 space-y-3">
                  {outline.sections.map((section, i) => (
                    <div key={i} className="p-3 border rounded">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{section.title}</span>
                        {section.duration && (
                          <Badge variant="outline">
                            <Clock className="h-3 w-3 mr-1" />
                            {section.duration}
                          </Badge>
                        )}
                      </div>
                      <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                        {section.bullets.map((bullet, j) => (
                          <li key={j}>{bullet}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>

              {/* CTA & Target */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Call to Action</label>
                  <Input value={outline.call_to_action} readOnly className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium">Target Audience</label>
                  <Input value={outline.target_audience} readOnly className="mt-1" />
                </div>
              </div>

              <div className="flex gap-2 pt-4">
                <Button variant="outline" onClick={() => setStep("overlap")}>
                  Back
                </Button>
                <Button
                  variant="outline"
                  onClick={() =>
                    copyToClipboard(
                      `${outline.title}\n\nHook: ${outline.hook}\n\n${outline.sections
                        .map(
                          (s) =>
                            `## ${s.title}\n${s.bullets.map((b) => `- ${b}`).join("\n")}`
                        )
                        .join("\n\n")}\n\nCTA: ${outline.call_to_action}`
                    )
                  }
                >
                  {copied ? <Check className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
                  Copy Outline
                </Button>
                <Button
                  onClick={handleGenerateScript}
                  disabled={loading}
                  className="flex-1"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  Generate Full Script
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Step 4: Script */}
      {step === "script" && script && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-purple-500" />
                {script.title}
              </CardTitle>
              <CardDescription className="flex items-center gap-4">
                <span>{script.word_count} words</span>
                <span>~{script.estimated_duration_minutes} minutes</span>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-sm bg-gray-50 p-4 rounded max-h-[500px] overflow-y-auto">
                  {script.full_script}
                </pre>
              </div>
              <div className="flex gap-2 mt-4">
                <Button variant="outline" onClick={() => setStep("outline")}>
                  Back to Outline
                </Button>
                <Button
                  variant="outline"
                  onClick={() => copyToClipboard(script.full_script)}
                >
                  {copied ? <Check className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
                  Copy Script
                </Button>
                <Button onClick={resetWizard} className="flex-1">
                  Start New Video
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

function SeriesPlanner() {
  const [seriesTopic, setSeriesTopic] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SeriesSuggestionResponse | null>(null)
  const [expandedSuggestion, setExpandedSuggestion] = useState<number | null>(null)

  const handleGetSuggestions = async () => {
    if (!seriesTopic.trim()) return
    setLoading(true)
    try {
      const data = await getSeriesSuggestions(seriesTopic)
      setResult(data)
    } catch (error) {
      console.error("Error getting suggestions:", error)
    }
    setLoading(false)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListChecks className="h-5 w-5 text-blue-500" />
            Series Planner
          </CardTitle>
          <CardDescription>
            Get episode suggestions for a video series based on your existing content
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Enter series topic (e.g., LinkedIn Optimization, Agentic Coding)"
              value={seriesTopic}
              onChange={(e) => setSeriesTopic(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGetSuggestions()}
            />
            <Button onClick={handleGetSuggestions} disabled={loading || !seriesTopic.trim()}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-6">
          {/* Series Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Series: {result.series_topic}</CardTitle>
              <CardDescription>{result.series_summary}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Existing Episodes */}
              {result.existing_episodes.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">
                    Existing Episodes ({result.existing_episodes.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {result.existing_episodes.map((ep) => (
                      <Badge key={ep.video_id} variant="outline">
                        {ep.title.slice(0, 40)}...
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Gaps */}
              {result.gaps_identified.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                    Content Gaps Identified
                  </h4>
                  <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                    {result.gaps_identified.map((gap, i) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Suggestions */}
          <Card>
            <CardHeader>
              <CardTitle>Suggested Episodes</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {result.suggestions.map((suggestion, i) => (
                  <div
                    key={i}
                    className="border rounded p-4 cursor-pointer hover:border-purple-300 transition-colors"
                    onClick={() =>
                      setExpandedSuggestion(expandedSuggestion === i ? null : i)
                    }
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center font-medium">
                          {i + 1}
                        </div>
                        <div>
                          <h4 className="font-medium">{suggestion.title}</h4>
                          <p className="text-sm text-gray-500 mt-1">
                            {suggestion.description}
                          </p>
                        </div>
                      </div>
                      {expandedSuggestion === i ? (
                        <ChevronDown className="h-5 w-5 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-gray-400" />
                      )}
                    </div>
                    {expandedSuggestion === i && (
                      <div className="mt-4 pt-4 border-t space-y-2">
                        {suggestion.builds_on && (
                          <div className="text-sm">
                            <span className="font-medium">Builds on:</span>{" "}
                            <span className="text-gray-600">{suggestion.builds_on}</span>
                          </div>
                        )}
                        <div className="text-sm">
                          <span className="font-medium">Unique Value:</span>{" "}
                          <span className="text-gray-600">{suggestion.unique_value}</span>
                        </div>
                        <Button
                          size="sm"
                          className="mt-2"
                          onClick={(e) => {
                            e.stopPropagation()
                            // Could navigate to wizard with this topic
                          }}
                        >
                          <Lightbulb className="h-4 w-4 mr-2" />
                          Create This Video
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

function ClipFinder() {
  const [videoId, setVideoId] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ClipCandidatesResponse | null>(null)

  const handleFindClips = async () => {
    if (!videoId.trim()) return
    setLoading(true)
    try {
      // Extract video ID if full URL provided
      let id = videoId.trim()
      if (id.includes("youtube.com") || id.includes("youtu.be")) {
        const match = id.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
        if (match) id = match[1]
      }
      const data = await getClipCandidates(id)
      setResult(data)
    } catch (error) {
      console.error("Error finding clips:", error)
    }
    setLoading(false)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Scissors className="h-5 w-5 text-red-500" />
            Clip Finder
          </CardTitle>
          <CardDescription>
            Find the best moments in your videos for shorts and clips
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Enter video ID or YouTube URL"
              value={videoId}
              onChange={(e) => setVideoId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFindClips()}
            />
            <Button onClick={handleFindClips} disabled={loading || !videoId.trim()}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Scissors className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Clip Candidates</CardTitle>
            <CardDescription>
              Found {result.clips.length} potential clips
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {result.clips.map((clip, i) => (
                <div key={i} className="border rounded p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h4 className="font-medium">{clip.suggested_title}</h4>
                      <div className="flex items-center gap-2 text-sm text-gray-500 mt-1">
                        <Video className="h-4 w-4" />
                        <span>
                          {clip.start_time} - {clip.end_time}
                        </span>
                      </div>
                    </div>
                    <Badge>{i + 1}</Badge>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="font-medium text-purple-600">Hook:</span>{" "}
                      <span className="italic">"{clip.hook}"</span>
                    </div>
                    <div>
                      <span className="font-medium">Content:</span>{" "}
                      {clip.content_summary}
                    </div>
                    <div>
                      <span className="font-medium text-green-600">Why it works:</span>{" "}
                      {clip.why_it_works}
                    </div>
                  </div>

                  <div className="flex gap-2 mt-4">
                    <Button size="sm" variant="outline">
                      <Copy className="h-4 w-4 mr-2" />
                      Copy Info
                    </Button>
                    <Button size="sm">
                      <Scissors className="h-4 w-4 mr-2" />
                      Create Short
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
