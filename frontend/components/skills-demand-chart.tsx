"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts"
import type { MatchResult } from "@/lib/job-data"

interface SkillsDemandChartProps {
  results: MatchResult[]
  userSkills: string[]
}

export function SkillsDemandChart({ results, userSkills }: SkillsDemandChartProps) {
  if (results.length === 0) return null

  // Count skill occurrences across all matched jobs
  const skillCount: Record<string, number> = {}
  results.forEach(r => {
    r.job.requiredSkills.forEach(skill => {
      skillCount[skill] = (skillCount[skill] || 0) + 1
    })
  })

  const normalizedUserSkills = userSkills.map(s => s.toLowerCase())

  const data = Object.entries(skillCount)
    .map(([skill, count]) => ({
      skill,
      count,
      hasSkill: normalizedUserSkills.includes(skill.toLowerCase())
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  return (
    <Card>
      <CardHeader>
        <CardTitle>What Your Top Matches Want</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="skill"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 13, fill: 'currentColor' }}
                width={75}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload
                    return (
                      <div className="rounded-lg border bg-popover px-3 py-2 shadow-md">
                        <p className="font-medium">{data.skill}</p>
                        <p className="text-sm text-muted-foreground">
                          Required in {data.count} job{data.count > 1 ? 's' : ''}
                        </p>
                        <p className={`text-sm font-medium ${data.hasSkill ? 'text-green-500' : 'text-orange-500'}`}>
                          {data.hasSkill ? '✓ You have this skill' : '✗ Skill to learn'}
                        </p>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Bar
                dataKey="count"
                radius={[0, 4, 4, 0]}
                maxBarSize={30}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.hasSkill ? 'hsl(142, 71%, 45%)' : 'hsl(24, 100%, 50%)'}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex items-center justify-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded bg-green-500" />
            <span className="text-muted-foreground">Skills you have</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded bg-orange-500" />
            <span className="text-muted-foreground">Skills to learn</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
