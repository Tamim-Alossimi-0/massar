"use client"

import { useState } from "react"
import { JobCard } from "@/components/job-card"
import { CompareBar } from "@/components/compare-bar"
import type { MatchResult } from "@/lib/job-data"

interface ResultsSectionProps {
  results: MatchResult[]
}

export function ResultsSection({ results }: ResultsSectionProps) {
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set())

  const toggleSelection = (jobId: string, selected: boolean) => {
    setSelectedJobs(prev => {
      const next = new Set(prev)
      if (selected && next.size < 3) {
        next.add(jobId)
      } else {
        next.delete(jobId)
      }
      return next
    })
  }

  const selectedResults = results.filter(r => selectedJobs.has(r.job.id))

  const clearSelection = () => setSelectedJobs(new Set())

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">
          Your Top Matches
          <span className="ml-2 text-lg font-normal text-muted-foreground">
            ({results.length} jobs)
          </span>
        </h2>
      </div>

      <div className="space-y-4">
        {results.map((result, index) => (
          <JobCard
            key={result.job.id}
            result={result}
            rank={index + 1}
            isSelected={selectedJobs.has(result.job.id)}
            onSelect={(selected) => toggleSelection(result.job.id, selected)}
          />
        ))}
      </div>

      {results.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-lg text-muted-foreground">No matching jobs found. Try adjusting your filters.</p>
        </div>
      )}

      <CompareBar
        selectedResults={selectedResults}
        onClear={clearSelection}
      />
    </section>
  )
}
