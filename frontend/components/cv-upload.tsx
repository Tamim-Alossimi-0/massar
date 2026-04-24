"use client"

import { useCallback, useState } from "react"
import { Upload, FileText, X, Sparkles } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { uploadCV } from "@/lib/api"

interface CVUploadProps {
  onUpload: (skills: string[], file: File) => void
  onDemo?:  () => void | Promise<void>
  isDemoRunning?: boolean
}

export function CVUpload({ onUpload, onDemo, isDemoRunning = false }: CVUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile && (droppedFile.type === "application/pdf" || droppedFile.type === "text/plain")) {
      setFile(droppedFile)
      setError(null)
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
      setError(null)
    }
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!file) return
    setIsProcessing(true)
    setError(null)
    try {
      const { skills } = await uploadCV(file)
      onUpload(skills, file)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to extract skills"
      setError(msg)
    } finally {
      setIsProcessing(false)
    }
  }, [file, onUpload])

  const clearFile = useCallback(() => {
    setFile(null)
    setError(null)
  }, [])

  return (
    <Card
      className={cn(
        "relative border-2 border-dashed transition-all duration-200",
        isDragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
        "p-8 md:p-12",
      )}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      {!file ? (
        <div className="flex flex-col items-center gap-6">
          <label className="flex cursor-pointer flex-col items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Upload className="h-8 w-8 text-primary" />
            </div>
            <div className="text-center">
              <p className="text-lg font-medium">Drop your CV here or click to browse</p>
              <p className="mt-1 text-sm text-muted-foreground">Supports PDF and TXT files</p>
            </div>
            <input
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>

          {onDemo && (
            <>
              <div className="flex w-full items-center gap-3 text-xs uppercase tracking-wider text-muted-foreground">
                <div className="h-px flex-1 bg-border" />
                <span>or</span>
                <div className="h-px flex-1 bg-border" />
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={(e) => { e.preventDefault(); void onDemo() }}
                disabled={isDemoRunning}
                className="gap-2"
              >
                {isDemoRunning ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Running Demo...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 text-primary" />
                    Try Demo with Sample CV
                  </>
                )}
              </Button>
              <p className="-mt-3 text-center text-xs text-muted-foreground">
                Loads a sample Data Scientist CV and runs a match instantly
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-3 rounded-lg bg-secondary px-4 py-3">
            <FileText className="h-6 w-6 text-primary" />
            <span className="font-medium">{file.name}</span>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={clearFile}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <Button
            onClick={handleAnalyze}
            disabled={isProcessing}
            className="bg-primary hover:bg-primary/90"
          >
            {isProcessing ? (
              <>
                <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                Analyzing CV...
              </>
            ) : (
              "Analyze CV"
            )}
          </Button>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
      )}
    </Card>
  )
}
