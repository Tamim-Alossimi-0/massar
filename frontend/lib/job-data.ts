// lib/job-data.ts
// UI-facing types + one mapper that converts a FastAPI match response into
// the MatchResult shape the existing components expect. All real data comes
// from lib/api.ts at runtime - no hardcoded job arrays live here anymore.

import type { ApiMatch } from "@/lib/api"

export interface Job {
  id: string
  title: string
  company: string
  location: string
  salary: string
  salaryMin: number
  salaryMax: number
  category: string
  seniority: string
  experienceMin: number
  experienceMax: number
  requiredSkills: string[]
  description: string
}

export interface MatchResult {
  job: Job
  overallScore: number      // 0..100
  semanticScore: number     // 0..100
  skillsScore: number       // 0..100
  experienceScore: number   // 0..100
  matchedSkills: string[]
  missingSkills: string[]
  explanation: string
  skillImportance: Record<string, string>
}

// -- Helpers --------------------------------------------------------------

const SALARY_RE = /([\d,]+)\s*[–\-~to]+\s*([\d,]+)/i

function parseSalary(raw: string): { min: number; max: number; display: string } {
  if (!raw) return { min: 0, max: 0, display: "Not disclosed" }
  const match = raw.match(SALARY_RE)
  if (!match) return { min: 0, max: 0, display: raw.trim() || "Not disclosed" }
  const min = parseInt(match[1].replace(/,/g, ""), 10)
  const max = parseInt(match[2].replace(/,/g, ""), 10)
  return {
    min,
    max,
    display: `${Math.round(min / 1000)}K - ${Math.round(max / 1000)}K SAR`,
  }
}

const CATEGORY_RULES: [string, RegExp][] = [
  ["Data Science",         /data scientist|data science/i],
  ["ML / AI",              /machine learning|\bml\b|\bai\b|deep learning|nlp/i],
  ["Analytics / BI",       /data analyst|business intelligence|\bbi\b|analytics/i],
  ["Data Engineering",     /data engineer|etl/i],
  ["DevOps / Cloud",       /devops|cloud|\bsre\b|site reliability|platform engineer/i],
  ["Cybersecurity",        /security|cyber|infosec|penetration/i],
  ["Frontend",             /frontend|front[- ]end/i],
  ["Backend",              /backend|back[- ]end/i],
  ["Full Stack",           /full[- ]?stack/i],
  ["Mobile",               /mobile|android|ios/i],
  ["Software Engineering", /software engineer|developer/i],
]

function categoriseTitle(title: string): string {
  for (const [label, rx] of CATEGORY_RULES) {
    if (rx.test(title)) return label
  }
  return "Other"
}

function seniorityFromYears(y: number): string {
  if (y < 2) return "entry"
  if (y < 4) return "junior"
  if (y < 7) return "mid"
  return "senior"
}

/**
 * Map a FastAPI /api/match row into the MatchResult shape used by
 * JobCard, CompareBar, GapReport, and the results list.
 */
export function mapApiMatch(m: ApiMatch, index: number): MatchResult {
  const salary = parseSalary(m.salary_range)
  const jobYears = Number(m.experience_years) || 0

  const job: Job = {
    id:            `${m.company}__${m.job_title}__${index}`,
    title:         m.job_title,
    company:       m.company || "Unknown",
    location:      m.location || "Riyadh",
    salary:        salary.display,
    salaryMin:     salary.min,
    salaryMax:     salary.max,
    category:      categoriseTitle(m.job_title),
    seniority:     seniorityFromYears(jobYears),
    experienceMin: Math.max(0, jobYears - 1),
    experienceMax: jobYears === 0 ? 99 : jobYears + 2,
    requiredSkills: Array.from(
      new Set([...(m.matched_skills ?? []), ...(m.missing_skills ?? [])]),
    ),
    description:   m.match_explanation || "",
  }

  return {
    job,
    overallScore:    Math.round((m.overall_score ?? 0) * 100),
    semanticScore:   Math.round((m.semantic_score ?? 0) * 100),
    skillsScore:     Math.round((m.skills_score ?? 0) * 100),
    experienceScore: Math.round((m.experience_score ?? 0) * 100),
    matchedSkills:   m.matched_skills ?? [],
    missingSkills:   m.missing_skills ?? [],
    explanation:     m.match_explanation ?? "",
    skillImportance: m.skill_importance ?? {},
  }
}
