"use client"

import { useState, useCallback } from "react"
import { Header } from "@/components/header"
import { CVUpload } from "@/components/cv-upload"
import { FeatureCards } from "@/components/feature-cards"
import { ConfigBar, type SearchConfig } from "@/components/config-bar"
import { ResultsSection } from "@/components/results-section"
import { GapReport } from "@/components/gap-report"
import { SkillsDemandChart } from "@/components/skills-demand-chart"
import { Skeleton } from "@/components/ui/skeleton"
import type { MatchResult } from "@/lib/job-data"
import { findMatches, uploadCV, type ApiMatch } from "@/lib/api"
import { DEMO_CV_TEXT, DEMO_CV_FILENAME } from "@/lib/demo-cv"

// Defaults used when the user triggers the demo instead of uploading.
const DEMO_EXPERIENCE_YEARS = 4
const DEMO_SENIORITY        = "All"

export default function HomePage() {
  const [cvFile, setCvFile]             = useState<File | null>(null)
  const [cvUploaded, setCvUploaded]     = useState(false)
  const [skills, setSkills]             = useState<string[]>([])
  const [results, setResults]           = useState<MatchResult[]>([])
  const [apiMatches, setApiMatches]     = useState<ApiMatch[]>([])
  const [lastSkills, setLastSkills]     = useState<string[]>([])
  const [lastExperience, setLastExp]    = useState<number>(0)
  const [isSearching, setIsSearching]   = useState(false)
  const [hasSearched, setHasSearched]   = useState(false)
  const [error, setError]               = useState<string | null>(null)
  const [isDemoRunning, setDemoRunning] = useState(false)

  const handleCVUpload = useCallback((extractedSkills: string[], file: File) => {
    setSkills(extractedSkills)
    setCvFile(file)
    setCvUploaded(true)
  }, [])

  /**
   * Demo flow: synthesize a File from the bundled sample CV, then fire
   * /api/skills/extract and /api/match in parallel so first-time visitors
   * see the full pipeline (skill badges + ranked matches) without needing
   * to upload anything.
   */
  const handleDemo = useCallback(async () => {
    if (isDemoRunning || isSearching) return
    setDemoRunning(true)
    setIsSearching(true)
    setError(null)

    const demoFile = new File([DEMO_CV_TEXT], DEMO_CV_FILENAME, {
      type: "text/plain",
    })

    try {
      const [{ skills: demoSkills }, matchResult] = await Promise.all([
        uploadCV(demoFile),
        findMatches({
          cvFile:      demoFile,
          skills:      [],                       // let server extract
          experience:  DEMO_EXPERIENCE_YEARS,
          seniority:   DEMO_SENIORITY,
          searchQuery: "",
          topN:        10,
        }),
      ])

      setCvFile(demoFile)
      setSkills(demoSkills)
      setCvUploaded(true)

      setResults(matchResult.matches)
      setApiMatches(matchResult.apiMatches)
      setLastSkills(demoSkills)
      setLastExp(DEMO_EXPERIENCE_YEARS)
      setHasSearched(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Demo run failed"
      setError(msg)
    } finally {
      setIsSearching(false)
      setDemoRunning(false)
    }
  }, [isDemoRunning, isSearching])

  const handleSearch = useCallback(async (config: SearchConfig) => {
    if (!cvFile) {
      setError("Upload a CV before searching.")
      return
    }
    setIsSearching(true)
    setError(null)

    try {
      const { matches, apiMatches } = await findMatches({
        cvFile,
        skills:      config.skills,
        experience:  config.experience,
        seniority:   config.seniority,
        searchQuery: config.searchQuery,
        topN:        10,
      })
      setResults(matches)
      setApiMatches(apiMatches)
      setLastSkills(config.skills)
      setLastExp(config.experience)
      setHasSearched(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Search failed"
      setError(msg)
    } finally {
      setIsSearching(false)
    }
  }, [cvFile])

  return (
    <div className="min-h-screen">
      <Header />

      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-900 via-slate-800 to-background" />
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.15) 1px, transparent 0)",
            backgroundSize: "40px 40px",
          }}
        />

        <div className="relative container mx-auto px-4 py-16 md:py-24">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-balance text-4xl font-bold tracking-tight text-white md:text-5xl lg:text-6xl">
              Your Career Path Starts Here
            </h1>
            <p className="mt-6 text-pretty text-lg text-slate-300 md:text-xl">
              AI-powered CV analysis matches you with the best tech roles in Riyadh using semantic similarity and skill analysis
            </p>
          </div>

          <div className="mx-auto mt-12 max-w-2xl">
            <CVUpload
              onUpload={handleCVUpload}
              onDemo={handleDemo}
              isDemoRunning={isDemoRunning}
            />
          </div>

          <div className="mx-auto mt-12 max-w-4xl">
            <FeatureCards />
          </div>
        </div>
      </section>

      {cvUploaded && (
        <section className="container mx-auto px-4 -mt-6 relative z-10">
          <ConfigBar
            skills={skills}
            onSkillsChange={setSkills}
            onSearch={handleSearch}
          />
        </section>
      )}

      {cvUploaded && (
        <main className="container mx-auto px-4 py-12 space-y-12">
          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {isSearching ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-48" />
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-64 w-full" />
              ))}
            </div>
          ) : hasSearched ? (
            <>
              <ResultsSection results={results} />

              {results.length > 0 && (
                <>
                  <GapReport
                    results={results}
                    userSkills={lastSkills}
                    apiMatches={apiMatches}
                    experienceYears={lastExperience}
                  />
                  <SkillsDemandChart results={results} userSkills={lastSkills} />
                </>
              )}
            </>
          ) : (
            <div className="py-12 text-center">
              <p className="text-lg text-muted-foreground">
                Configure your preferences above and click &quot;Find Matches&quot; to see your job matches
              </p>
            </div>
          )}
        </main>
      )}

      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Massar - AI-Powered Job Matching Platform</p>
        </div>
      </footer>
    </div>
  )
}
