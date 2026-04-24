"use client"

import { useEffect, useState } from "react"
import { Download, TrendingUp, Target, BookOpen, DollarSign } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import type { MatchResult } from "@/lib/job-data"
import {
  getGapReport,
  type ApiMatch,
  type GapReport as GapReportData,
} from "@/lib/api"

interface GapReportProps {
  results:         MatchResult[]
  userSkills:      string[]
  apiMatches:      ApiMatch[]
  experienceYears: number
}

export function GapReport({ results, userSkills, apiMatches, experienceYears }: GapReportProps) {
  const [report,  setReport]  = useState<GapReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    if (apiMatches.length === 0) {
      setReport(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getGapReport(apiMatches, userSkills, experienceYears)
      .then((r) => { if (!cancelled) setReport(r) })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Gap report failed")
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [apiMatches, userSkills, experienceYears])

  if (results.length === 0) return null

  const handleDownload = () => {
    if (!report) return
    const blob = new Blob([report.text_report], { type: "text/plain;charset=utf-8" })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement("a")
    a.href     = url
    a.download = `cv_gap_report_${report.generated_on}.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const importanceColor = (imp: string) => {
    if (imp === "high")   return "bg-red-500/10 text-red-600 dark:text-red-400"
    if (imp === "medium") return "bg-blue-500/10 text-blue-600 dark:text-blue-400"
    return "bg-slate-500/10 text-slate-600 dark:text-slate-400"
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          Your Career Gap Report
        </CardTitle>
        <Button
          variant="outline"
          size="sm"
          disabled={!report}
          onClick={handleDownload}
        >
          <Download className="mr-2 h-4 w-4" />
          Download Report
        </Button>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="grid gap-4 md:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        {report && (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <TrendingUp className="h-4 w-4" />
                Best Matching Category
              </div>
              <p className="text-2xl font-bold">{report.top_role}</p>
              <p className="text-sm text-muted-foreground">
                Across top {report.match_count} matches
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Target className="h-4 w-4" />
                Skills Coverage
              </div>
              <p className="text-2xl font-bold">
                {report.cv_skills_covered}/{report.total_unique_skills}
              </p>
              <p className="text-sm text-muted-foreground">
                {report.total_unique_skills > 0
                  ? Math.round((report.cv_skills_covered / report.total_unique_skills) * 100)
                  : 0}
                % of requirements
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <DollarSign className="h-4 w-4" />
                Estimated Salary Range
              </div>
              {report.salary ? (
                <>
                  <p className="text-2xl font-bold">
                    {Math.round(report.salary.avg_min / 1000)}K -{" "}
                    {Math.round(report.salary.avg_max / 1000)}K
                  </p>
                  <p className="text-sm text-muted-foreground">
                    SAR/month ({report.salary.sample_n} listings)
                  </p>
                </>
              ) : (
                <>
                  <p className="text-2xl font-bold">-</p>
                  <p className="text-sm text-muted-foreground">
                    No salary data in matches
                  </p>
                </>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <BookOpen className="h-4 w-4" />
                Top Skills to Learn
              </div>
              <div className="flex flex-wrap gap-1.5">
                {report.top_missing.length === 0 && (
                  <span className="text-sm text-muted-foreground">
                    You cover the core requirements.
                  </span>
                )}
                {report.top_missing.map((item) => (
                  <Badge
                    key={item.skill}
                    variant="secondary"
                    className={importanceColor(item.importance)}
                  >
                    {item.skill}
                    <span className="ml-1 text-xs opacity-70">
                      {item.jobs_requiring}/{report.match_count}
                    </span>
                  </Badge>
                ))}
              </div>
              {report.top_missing.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  Adding these could lift your match by ~
                  {report.estimated_boost_pct}%
                </p>
              )}
            </div>

            {report.experience_gap && (
              <div className="md:col-span-2 lg:col-span-4 rounded-lg bg-yellow-500/10 border border-yellow-500/30 p-4">
                <p className="text-sm">
                  Most matching roles require ~
                  <span className="font-semibold">{report.experience_gap.avg_required}</span>{" "}
                  years. You have{" "}
                  <span className="font-semibold">{report.experience_gap.user_has}</span>{" "}
                  years. Consider targeting{" "}
                  <span className="font-semibold">
                    {report.experience_gap.suggested_tier}
                  </span>{" "}
                  tier roles first.
                </p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
