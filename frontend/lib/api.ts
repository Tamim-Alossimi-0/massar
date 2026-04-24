// lib/api.ts - REST client for the FastAPI backend.
// In dev, requests go to /api/* and next.config.mjs proxies to localhost:8000.
// In prod, point NEXT_PUBLIC_API_URL at the deployed backend.

import type { MatchResult } from "@/lib/job-data"
import { mapApiMatch } from "@/lib/job-data"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

// -- Shared error helper --------------------------------------------------

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      // ignore parse errors
    }
    throw new ApiError(detail, res.status)
  }
  return res.json() as Promise<T>
}

// -- Raw API response shapes ---------------------------------------------

export interface ApiMatch {
  job_title: string
  company: string
  location: string
  salary_range: string
  experience_years: number
  overall_score: number     // 0..1
  semantic_score: number    // 0..1
  skills_score: number      // 0..1
  experience_score: number  // 0..1
  match_explanation: string
  matched_skills: string[]
  missing_skills: string[]
  skill_importance: Record<string, string>
}

interface MatchApiResponse {
  matches: ApiMatch[]
  total_candidates: number
  filters_applied: { keyword: string; seniority: string }
}

export interface MarketStats {
  total_jobs: number
  unique_companies: number
  top_skills: { skill: string; count: number }[]
  jobs_by_category: { category: string; count: number }[]
  salary_by_category: { category: string; avg_min: number; avg_max: number; sample_n: number }[]
  experience_distribution: { bucket: string; count: number }[]
  top_companies: { company: string; count: number }[]
}

export interface GapReport {
  candidate_name: string
  generated_on: string
  top_role: string
  role_distribution: Record<string, number>
  cv_skills_covered: number
  total_unique_skills: number
  seniority: string
  experience_years: number
  top_missing: { skill: string; jobs_requiring: number; importance: string }[]
  estimated_boost_pct: number
  salary: { avg_min: number; avg_max: number; sample_n: number } | null
  experience_gap: { avg_required: number; user_has: number; suggested_tier: string } | null
  match_count: number
  text_report: string
}

export interface RefreshResult {
  success: boolean
  job_count: number
  message: string
}

// -- Config passed from the UI to findMatches ----------------------------

export interface MatchConfig {
  cvFile?: File
  cvText?: string
  skills: string[]
  experience: number
  seniority: string           // "All" | "Entry" | "Junior" | "Mid" | "Senior"
  searchQuery: string
  topN?: number
}

// -- 1. Real-time skill extraction from an uploaded CV -------------------

export interface CVUploadResult {
  skills:  string[]
  cv_text: string
}

/**
 * Uploads the CV to the backend which parses PDF/TXT server-side (via
 * pdfplumber) and extracts skills. Returns both the skill list and the
 * parsed text so callers can reuse it without shipping a PDF parser to
 * the browser.
 */
export async function uploadCV(file: File): Promise<CVUploadResult> {
  const form = new FormData()
  form.append("file", file)

  const res = await fetch(`${API_BASE}/api/skills/extract`, {
    method: "POST",
    body:   form,
  })
  const data = await jsonOrThrow<CVUploadResult>(res)
  return {
    skills:  data.skills  ?? [],
    cv_text: data.cv_text ?? "",
  }
}

// -- 2. Rank jobs against the CV -----------------------------------------

export async function findMatches(config: MatchConfig): Promise<{
  matches: MatchResult[]
  apiMatches: ApiMatch[]
  totalCandidates: number
}> {
  const form = new FormData()
  form.append("experience_years", String(config.experience))
  form.append("seniority_label",  config.seniority || "All")
  form.append("keyword_search",   config.searchQuery || "")
  form.append("top_n",            String(config.topN ?? 10))

  for (const s of config.skills) form.append("user_skills", s)

  if (config.cvFile) {
    form.append("cv_file", config.cvFile)
  } else if (config.cvText && config.cvText.trim()) {
    form.append("cv_text", config.cvText)
  } else {
    throw new Error("findMatches requires either cvFile or cvText")
  }

  const res = await fetch(`${API_BASE}/api/match`, {
    method: "POST",
    body:   form,
  })
  const data = await jsonOrThrow<MatchApiResponse>(res)
  const matches = (data.matches ?? []).map((m, i) => mapApiMatch(m, i))
  return {
    matches,
    apiMatches:      data.matches ?? [],
    totalCandidates: data.total_candidates ?? 0,
  }
}

// -- 3. Market dashboard aggregates --------------------------------------

export async function getMarketStats(): Promise<MarketStats> {
  const res = await fetch(`${API_BASE}/api/jobs/stats`)
  return jsonOrThrow<MarketStats>(res)
}

// -- 4. CV gap report ----------------------------------------------------

export async function getGapReport(
  apiMatches: ApiMatch[],
  cvSkills: string[],
  experienceYears: number,
  cvText = "",
): Promise<GapReport> {
  const res = await fetch(`${API_BASE}/api/gap-report`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({
      matches:          apiMatches,
      cv_skills:        cvSkills,
      experience_years: experienceYears,
      cv_text:          cvText,
    }),
  })
  return jsonOrThrow<GapReport>(res)
}

// -- 5. Trigger collector pipeline ---------------------------------------

export async function refreshJobs(): Promise<RefreshResult> {
  const res = await fetch(`${API_BASE}/api/jobs/refresh`, { method: "POST" })
  return jsonOrThrow<RefreshResult>(res)
}

export { ApiError }
