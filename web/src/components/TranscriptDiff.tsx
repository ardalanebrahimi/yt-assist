import { useState, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check, X, Upload, Save, Eye, EyeOff, ChevronDown, ChevronUp } from "lucide-react"

interface TranscriptDiffProps {
  original: string
  cleaned: string
  changesSummary?: string
  onAccept: (cleaned: string) => void
  onReject: () => void
  onUploadToYouTube: (cleaned: string) => void
  onSave: (cleaned: string) => void
  isUploading?: boolean
  isSaving?: boolean
}

// Simple word-level diff algorithm
function computeWordDiff(oldText: string, newText: string): { type: 'equal' | 'delete' | 'insert', text: string }[] {
  const oldWords = oldText.split(/(\s+)/)
  const newWords = newText.split(/(\s+)/)

  // LCS-based diff
  const m = oldWords.length
  const n = newWords.length
  const dp: number[][] = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldWords[i - 1] === newWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  // Backtrack to find diff
  const result: { type: 'equal' | 'delete' | 'insert', text: string }[] = []
  let i = m, j = n
  const temp: { type: 'equal' | 'delete' | 'insert', text: string }[] = []

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
      temp.push({ type: 'equal', text: oldWords[i - 1] })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      temp.push({ type: 'insert', text: newWords[j - 1] })
      j--
    } else {
      temp.push({ type: 'delete', text: oldWords[i - 1] })
      i--
    }
  }

  // Reverse and merge consecutive same-type segments
  for (let k = temp.length - 1; k >= 0; k--) {
    const item = temp[k]
    if (result.length > 0 && result[result.length - 1].type === item.type) {
      result[result.length - 1].text += item.text
    } else {
      result.push({ ...item })
    }
  }

  return result
}

// Compute line-by-line diff
function computeLineDiff(oldLines: string[], newLines: string[]): {
  type: 'equal' | 'delete' | 'insert' | 'modify'
  oldLine?: string
  newLine?: string
  oldIndex?: number
  newIndex?: number
  wordDiff?: { type: 'equal' | 'delete' | 'insert', text: string }[]
}[] {
  const m = oldLines.length
  const n = newLines.length
  const dp: number[][] = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))

  // Build LCS table
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1].trim() === newLines[j - 1].trim()) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  // Backtrack
  const result: {
    type: 'equal' | 'delete' | 'insert' | 'modify'
    oldLine?: string
    newLine?: string
    oldIndex?: number
    newIndex?: number
    wordDiff?: { type: 'equal' | 'delete' | 'insert', text: string }[]
  }[] = []

  let i = m, j = n
  const temp: typeof result = []

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1].trim() === newLines[j - 1].trim()) {
      temp.push({ type: 'equal', oldLine: oldLines[i - 1], newLine: newLines[j - 1], oldIndex: i - 1, newIndex: j - 1 })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      // Check if this is a modification (similar line exists nearby)
      if (i > 0 && isSimilar(oldLines[i - 1], newLines[j - 1])) {
        temp.push({
          type: 'modify',
          oldLine: oldLines[i - 1],
          newLine: newLines[j - 1],
          oldIndex: i - 1,
          newIndex: j - 1,
          wordDiff: computeWordDiff(oldLines[i - 1], newLines[j - 1])
        })
        i--
        j--
      } else {
        temp.push({ type: 'insert', newLine: newLines[j - 1], newIndex: j - 1 })
        j--
      }
    } else {
      temp.push({ type: 'delete', oldLine: oldLines[i - 1], oldIndex: i - 1 })
      i--
    }
  }

  return temp.reverse()
}

// Check if two lines are similar enough to be considered a modification
function isSimilar(a: string, b: string): boolean {
  const aWords = a.trim().split(/\s+/)
  const bWords = b.trim().split(/\s+/)

  if (aWords.length === 0 || bWords.length === 0) return false

  // Count matching words
  let matches = 0
  for (const word of aWords) {
    if (bWords.includes(word)) matches++
  }

  const similarity = matches / Math.max(aWords.length, bWords.length)
  return similarity > 0.3 // 30% similar words = modification
}

export function TranscriptDiff({
  original,
  cleaned,
  changesSummary,
  onAccept,
  onReject,
  onUploadToYouTube,
  onSave,
  isUploading = false,
  isSaving = false,
}: TranscriptDiffProps) {
  const [viewMode, setViewMode] = useState<'split' | 'unified'>('split')
  const [showUnchanged, setShowUnchanged] = useState(true)

  const lineDiff = useMemo(() => {
    const oldLines = original.split("\n")
    const newLines = cleaned.split("\n")
    return computeLineDiff(oldLines, newLines)
  }, [original, cleaned])

  const stats = useMemo(() => {
    let added = 0, removed = 0, modified = 0
    lineDiff.forEach(d => {
      if (d.type === 'insert') added++
      else if (d.type === 'delete') removed++
      else if (d.type === 'modify') modified++
    })
    return { added, removed, modified }
  }, [lineDiff])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h4 className="font-medium">Transcript Comparison</h4>
          <Badge variant="secondary" className="text-xs bg-green-100 text-green-800">
            +{stats.added}
          </Badge>
          <Badge variant="secondary" className="text-xs bg-red-100 text-red-800">
            -{stats.removed}
          </Badge>
          <Badge variant="secondary" className="text-xs bg-yellow-100 text-yellow-800">
            ~{stats.modified}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowUnchanged(!showUnchanged)}
          >
            {showUnchanged ? <ChevronUp className="h-4 w-4 mr-1" /> : <ChevronDown className="h-4 w-4 mr-1" />}
            {showUnchanged ? "Hide unchanged" : "Show all"}
          </Button>
          <Button
            variant={viewMode === 'split' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('split')}
          >
            Split
          </Button>
          <Button
            variant={viewMode === 'unified' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('unified')}
          >
            Unified
          </Button>
        </div>
      </div>

      {/* Diff View */}
      <div className="border rounded-md max-h-[500px] overflow-auto text-sm font-mono">
        {viewMode === 'split' ? (
          <div className="grid grid-cols-2">
            {/* Headers */}
            <div className="sticky top-0 bg-red-50 dark:bg-red-900/30 px-3 py-2 border-b border-r font-medium text-red-800 dark:text-red-200">
              Original
            </div>
            <div className="sticky top-0 bg-green-50 dark:bg-green-900/30 px-3 py-2 border-b font-medium text-green-800 dark:text-green-200">
              Cleaned
            </div>

            {/* Content */}
            {lineDiff.map((diff, idx) => {
              if (!showUnchanged && diff.type === 'equal') return null

              return (
                <div key={idx} className="contents">
                  {/* Left side (original) */}
                  <div className={`px-2 py-1 border-r ${
                    diff.type === 'delete' ? 'bg-red-100 dark:bg-red-900/40' :
                    diff.type === 'modify' ? 'bg-yellow-50 dark:bg-yellow-900/20' :
                    diff.type === 'insert' ? 'bg-gray-50 dark:bg-gray-800' :
                    ''
                  }`}>
                    <span className="text-muted-foreground text-xs mr-2 select-none inline-block w-6">
                      {diff.oldIndex !== undefined ? diff.oldIndex + 1 : ''}
                    </span>
                    {diff.type === 'modify' && diff.wordDiff ? (
                      <span>
                        {diff.wordDiff.map((w, i) => (
                          <span key={i} className={
                            w.type === 'delete' ? 'bg-red-200 dark:bg-red-800 line-through' :
                            w.type === 'insert' ? '' : ''
                          }>
                            {w.type !== 'insert' ? w.text : ''}
                          </span>
                        ))}
                      </span>
                    ) : (
                      <span className={diff.type === 'delete' ? 'text-red-800 dark:text-red-200' : ''}>
                        {diff.oldLine || '\u00A0'}
                      </span>
                    )}
                  </div>

                  {/* Right side (cleaned) */}
                  <div className={`px-2 py-1 ${
                    diff.type === 'insert' ? 'bg-green-100 dark:bg-green-900/40' :
                    diff.type === 'modify' ? 'bg-yellow-50 dark:bg-yellow-900/20' :
                    diff.type === 'delete' ? 'bg-gray-50 dark:bg-gray-800' :
                    ''
                  }`}>
                    <span className="text-muted-foreground text-xs mr-2 select-none inline-block w-6">
                      {diff.newIndex !== undefined ? diff.newIndex + 1 : ''}
                    </span>
                    {diff.type === 'modify' && diff.wordDiff ? (
                      <span>
                        {diff.wordDiff.map((w, i) => (
                          <span key={i} className={
                            w.type === 'insert' ? 'bg-green-200 dark:bg-green-800' :
                            w.type === 'delete' ? '' : ''
                          }>
                            {w.type !== 'delete' ? w.text : ''}
                          </span>
                        ))}
                      </span>
                    ) : (
                      <span className={diff.type === 'insert' ? 'text-green-800 dark:text-green-200' : ''}>
                        {diff.newLine || '\u00A0'}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          /* Unified view */
          <div>
            <div className="sticky top-0 bg-muted px-3 py-2 border-b font-medium">
              Unified Diff
            </div>
            {lineDiff.map((diff, idx) => {
              if (!showUnchanged && diff.type === 'equal') return null

              if (diff.type === 'equal') {
                return (
                  <div key={idx} className="px-2 py-1 flex">
                    <span className="text-muted-foreground text-xs w-12 flex-shrink-0">
                      {diff.oldIndex !== undefined ? diff.oldIndex + 1 : ''}
                    </span>
                    <span className="flex-1">{diff.oldLine}</span>
                  </div>
                )
              }

              if (diff.type === 'delete') {
                return (
                  <div key={idx} className="px-2 py-1 flex bg-red-100 dark:bg-red-900/40">
                    <span className="text-red-600 w-4">-</span>
                    <span className="text-muted-foreground text-xs w-8 flex-shrink-0">
                      {diff.oldIndex !== undefined ? diff.oldIndex + 1 : ''}
                    </span>
                    <span className="flex-1 text-red-800 dark:text-red-200">{diff.oldLine}</span>
                  </div>
                )
              }

              if (diff.type === 'insert') {
                return (
                  <div key={idx} className="px-2 py-1 flex bg-green-100 dark:bg-green-900/40">
                    <span className="text-green-600 w-4">+</span>
                    <span className="text-muted-foreground text-xs w-8 flex-shrink-0">
                      {diff.newIndex !== undefined ? diff.newIndex + 1 : ''}
                    </span>
                    <span className="flex-1 text-green-800 dark:text-green-200">{diff.newLine}</span>
                  </div>
                )
              }

              if (diff.type === 'modify') {
                return (
                  <div key={idx}>
                    <div className="px-2 py-1 flex bg-red-50 dark:bg-red-900/20">
                      <span className="text-red-600 w-4">-</span>
                      <span className="text-muted-foreground text-xs w-8 flex-shrink-0">
                        {diff.oldIndex !== undefined ? diff.oldIndex + 1 : ''}
                      </span>
                      <span className="flex-1">
                        {diff.wordDiff?.map((w, i) => (
                          <span key={i} className={w.type === 'delete' ? 'bg-red-200 dark:bg-red-800' : ''}>
                            {w.type !== 'insert' ? w.text : ''}
                          </span>
                        ))}
                      </span>
                    </div>
                    <div className="px-2 py-1 flex bg-green-50 dark:bg-green-900/20">
                      <span className="text-green-600 w-4">+</span>
                      <span className="text-muted-foreground text-xs w-8 flex-shrink-0">
                        {diff.newIndex !== undefined ? diff.newIndex + 1 : ''}
                      </span>
                      <span className="flex-1">
                        {diff.wordDiff?.map((w, i) => (
                          <span key={i} className={w.type === 'insert' ? 'bg-green-200 dark:bg-green-800' : ''}>
                            {w.type !== 'delete' ? w.text : ''}
                          </span>
                        ))}
                      </span>
                    </div>
                  </div>
                )
              }

              return null
            })}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-2 border-t">
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onReject}
            className="text-red-600 hover:text-red-700"
          >
            <X className="h-4 w-4 mr-1" />
            Discard
          </Button>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSave(cleaned)}
            disabled={isSaving}
          >
            <Save className="h-4 w-4 mr-1" />
            {isSaving ? "Saving..." : "Save"}
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={() => onUploadToYouTube(cleaned)}
            disabled={isUploading}
          >
            <Upload className="h-4 w-4 mr-1" />
            {isUploading ? "Uploading..." : "Upload to YouTube"}
          </Button>
        </div>
      </div>
    </div>
  )
}
