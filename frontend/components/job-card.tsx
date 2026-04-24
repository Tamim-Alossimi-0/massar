"use client"

import { useState } from "react"
import { MapPin, DollarSign, ChevronDown, ChevronUp, Info } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import type { MatchResult } from "@/lib/job-data"

interface JobCardProps {
  result: MatchResult
  rank: number
  isSelected: boolean
  onSelect: (selected: boolean) => void
}

export function JobCard({ result, rank, isSelected, onSelect }: JobCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const { job, overallScore, semanticScore, skillsScore, experienceScore, matchedSkills, missingSkills, explanation } = result

  const getBorderColor = () => {
    if (overallScore >= 65) return "border-l-green-500"
    if (overallScore >= 40) return "border-l-yellow-500"
    return "border-l-red-500"
  }

  const getScoreColor = () => {
    if (overallScore >= 65) return "text-green-500"
    if (overallScore >= 40) return "text-yellow-500"
    return "text-red-500"
  }

  return (
    <Card className={cn(
      "border-l-4 transition-all duration-200 hover:shadow-lg",
      getBorderColor()
    )}>
      <CardContent className="p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          {/* Left Section */}
          <div className="flex items-start gap-4">
            <div className="flex items-center gap-3">
              <Checkbox
                checked={isSelected}
                onCheckedChange={onSelect}
                aria-label={`Select ${job.title} for comparison`}
              />
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                #{rank}
              </div>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold">{job.title}</h3>
              <p className="text-muted-foreground">{job.company}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="secondary" className="gap-1">
                  <MapPin className="h-3 w-3" />
                  {job.location}
                </Badge>
                <Badge variant="secondary" className="gap-1">
                  <DollarSign className="h-3 w-3" />
                  {job.salary}
                </Badge>
              </div>
            </div>
          </div>

          {/* Score Circle */}
          <div className="flex items-center justify-center lg:justify-end">
            <div className="relative flex h-24 w-24 items-center justify-center">
              <svg className="h-24 w-24 -rotate-90 transform">
                <circle
                  cx="48"
                  cy="48"
                  r="40"
                  className="fill-none stroke-muted"
                  strokeWidth="8"
                />
                <circle
                  cx="48"
                  cy="48"
                  r="40"
                  className={cn("fill-none", getScoreColor().replace("text-", "stroke-"))}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${overallScore * 2.51} 251`}
                />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className={cn("text-2xl font-bold", getScoreColor())}>{overallScore}%</span>
                <span className="text-xs text-muted-foreground">Match</span>
              </div>
            </div>
          </div>
        </div>

        {/* Score Bars */}
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Semantic</span>
              <span className="font-medium">{semanticScore}%</span>
            </div>
            <Progress value={semanticScore} className="h-2" />
          </div>
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Skills</span>
              <span className="font-medium">{skillsScore}%</span>
            </div>
            <Progress value={skillsScore} className="h-2" />
          </div>
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Experience</span>
              <span className="font-medium">{experienceScore}%</span>
            </div>
            <Progress value={experienceScore} className="h-2" />
          </div>
        </div>

        {/* Skills */}
        <div className="mt-4 flex flex-wrap gap-2">
          {matchedSkills.map((skill) => (
            <Badge key={skill} className="bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20">
              {skill}
            </Badge>
          ))}
          {missingSkills.map((skill) => (
            <Badge key={skill} variant="outline" className="border-orange-500/50 text-orange-600 dark:text-orange-400">
              {skill}
              <span className="ml-1 text-xs opacity-70">To Learn</span>
            </Badge>
          ))}
        </div>

        {/* Explanation */}
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-muted/50 p-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{explanation}</p>
        </div>

        {/* Expandable Details */}
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="mt-4 w-full" size="sm">
              {isExpanded ? (
                <>
                  <ChevronUp className="mr-2 h-4 w-4" />
                  Hide Details
                </>
              ) : (
                <>
                  <ChevronDown className="mr-2 h-4 w-4" />
                  View Details
                </>
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4">
            <div className="rounded-lg bg-muted/30 p-4">
              <h4 className="mb-2 font-medium">Job Description</h4>
              <p className="text-sm text-muted-foreground">{job.description}</p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <span className="text-sm font-medium">Category:</span>
                  <span className="ml-2 text-sm text-muted-foreground">{job.category}</span>
                </div>
                <div>
                  <span className="text-sm font-medium">Seniority:</span>
                  <span className="ml-2 text-sm capitalize text-muted-foreground">{job.seniority}</span>
                </div>
                <div>
                  <span className="text-sm font-medium">Experience Required:</span>
                  <span className="ml-2 text-sm text-muted-foreground">{job.experienceMin}-{job.experienceMax} years</span>
                </div>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  )
}
