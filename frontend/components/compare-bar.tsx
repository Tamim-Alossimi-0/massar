"use client"

import { useState } from "react"
import { X, GitCompare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { MatchResult } from "@/lib/job-data"

interface CompareBarProps {
  selectedResults: MatchResult[]
  onClear: () => void
}

export function CompareBar({ selectedResults, onClear }: CompareBarProps) {
  const [open, setOpen] = useState(false)

  if (selectedResults.length < 2) return null

  return (
    <>
      <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transform">
        <div className="flex items-center gap-4 rounded-full border bg-card px-6 py-3 shadow-lg">
          <span className="text-sm font-medium">
            {selectedResults.length} jobs selected
          </span>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-full bg-primary hover:bg-primary/90">
                <GitCompare className="mr-2 h-4 w-4" />
                Compare Jobs
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[90vh] max-w-4xl overflow-auto">
              <DialogHeader>
                <DialogTitle>Job Comparison</DialogTitle>
              </DialogHeader>
              <ComparisonTable results={selectedResults} />
            </DialogContent>
          </Dialog>
          <Button variant="ghost" size="icon" onClick={onClear}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </>
  )
}

function ComparisonTable({ results }: { results: MatchResult[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b">
            <th className="p-3 text-left font-medium text-muted-foreground">Attribute</th>
            {results.map((r) => (
              <th key={r.job.id} className="p-3 text-left font-medium">
                {r.job.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Company</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">{r.job.company}</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Location</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">{r.job.location}</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Salary</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">{r.job.salary}</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Overall Match</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">
                <span className={cn(
                  "font-bold",
                  r.overallScore >= 65 ? "text-green-500" :
                  r.overallScore >= 40 ? "text-yellow-500" : "text-red-500"
                )}>
                  {r.overallScore}%
                </span>
              </td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Semantic Score</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">{r.semanticScore}%</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Skills Score</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">{r.skillsScore}%</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 text-muted-foreground">Experience Score</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">{r.experienceScore}%</td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 align-top text-muted-foreground">Matched Skills</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">
                <div className="flex flex-wrap gap-1">
                  {r.matchedSkills.map((skill) => (
                    <Badge key={skill} className="bg-green-500/10 text-green-600 dark:text-green-400 text-xs">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </td>
            ))}
          </tr>
          <tr className="border-b">
            <td className="p-3 align-top text-muted-foreground">Missing Skills</td>
            {results.map((r) => (
              <td key={r.job.id} className="p-3">
                <div className="flex flex-wrap gap-1">
                  {r.missingSkills.map((skill) => (
                    <Badge key={skill} variant="outline" className="border-orange-500/50 text-orange-600 dark:text-orange-400 text-xs">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}
