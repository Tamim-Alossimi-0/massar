"use client"

import { useEffect, useMemo, useState } from "react"
import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts"
import {
  Briefcase, Building2, DollarSign, TrendingUp, RefreshCw,
} from "lucide-react"
import { getMarketStats, refreshJobs, type MarketStats } from "@/lib/api"

export default function DashboardPage() {
  const [stats,       setStats]      = useState<MarketStats | null>(null)
  const [loading,     setLoading]    = useState(true)
  const [error,       setError]      = useState<string | null>(null)
  const [refreshing,  setRefreshing] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setStats(await getMarketStats())
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load market stats")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      await refreshJobs()
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed")
    } finally {
      setRefreshing(false)
    }
  }

  // Derived chart-ready slices
  const skillDemand = stats?.top_skills ?? []

  const salaryByCategory = useMemo(
    () => (stats?.salary_by_category ?? [])
      .map((s) => ({
        category: s.category,
        min: Math.round(s.avg_min / 1000),
        max: Math.round(s.avg_max / 1000),
        avg: Math.round(((s.avg_min + s.avg_max) / 2) / 1000),
      }))
      .sort((a, b) => b.avg - a.avg),
    [stats],
  )

  const experienceDistribution = useMemo(
    () => (stats?.experience_distribution ?? []).map((e) => ({
      level: e.bucket, count: e.count,
    })),
    [stats],
  )

  const topCompanies = stats?.top_companies ?? []

  const topRole = stats?.jobs_by_category?.[0]?.category ?? "-"
  const avgSalary = salaryByCategory.length
    ? Math.round(
        salaryByCategory.reduce((s, r) => s + r.avg, 0) / salaryByCategory.length,
      )
    : 0

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-3xl font-bold">Market Dashboard</h1>
          <Button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            variant="outline"
            size="sm"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Collecting real jobs..." : "Refresh Job Data"}
          </Button>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* KPI Cards */}
        <div className="mb-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <KpiCard icon={<Briefcase className="h-6 w-6 text-primary" />}
                   label="Total Jobs"
                   value={loading ? null : stats?.total_jobs?.toLocaleString()} />
          <KpiCard icon={<Building2 className="h-6 w-6 text-blue-500" />}
                   label="Companies"
                   value={loading ? null : stats?.unique_companies?.toLocaleString()}
                   tint="bg-blue-500/10" />
          <KpiCard icon={<DollarSign className="h-6 w-6 text-green-500" />}
                   label="Avg Salary"
                   value={loading ? null : (avgSalary ? `${avgSalary}K SAR` : "-")}
                   tint="bg-green-500/10" />
          <KpiCard icon={<TrendingUp className="h-6 w-6 text-yellow-500" />}
                   label="Top Role"
                   value={loading ? null : topRole}
                   tint="bg-yellow-500/10" />
        </div>

        {/* Charts */}
        <Card className="mb-6">
          <CardHeader><CardTitle>Top 15 In-Demand Skills</CardTitle></CardHeader>
          <CardContent>
            <div className="h-[400px]">
              {loading ? (
                <Skeleton className="h-full w-full" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={skillDemand}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                  >
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="skill"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: "currentColor" }}
                      width={75}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload
                          return (
                            <div className="rounded-lg border bg-popover px-3 py-2 shadow-md">
                              <p className="font-medium">{d.skill}</p>
                              <p className="text-sm text-muted-foreground">
                                Required in {d.count} job{d.count > 1 ? "s" : ""}
                              </p>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <Bar
                      dataKey="count"
                      fill="hsl(142, 71%, 45%)"
                      radius={[0, 4, 4, 0]}
                      maxBarSize={25}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="mb-8 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Salary by Role Category (K SAR)</CardTitle></CardHeader>
            <CardContent>
              <div className="h-[300px]">
                {loading ? (
                  <Skeleton className="h-full w-full" />
                ) : salaryByCategory.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No salary data.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={salaryByCategory}
                      margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    >
                      <XAxis
                        dataKey="category"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 12, fill: "currentColor" }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 12, fill: "currentColor" }}
                      />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const d = payload[0].payload
                            return (
                              <div className="rounded-lg border bg-popover px-3 py-2 shadow-md">
                                <p className="font-medium">{d.category}</p>
                                <p className="text-sm text-muted-foreground">Min: {d.min}K SAR</p>
                                <p className="text-sm text-muted-foreground">Max: {d.max}K SAR</p>
                                <p className="text-sm font-medium text-primary">Avg: {d.avg}K SAR</p>
                              </div>
                            )
                          }
                          return null
                        }}
                      />
                      <Bar dataKey="min" fill="hsl(200, 70%, 50%)" name="Min" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="avg" fill="hsl(142, 71%, 45%)" name="Avg" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="max" fill="hsl(250, 60%, 60%)" name="Max" radius={[4, 4, 0, 0]} />
                      <Legend />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Experience Distribution</CardTitle></CardHeader>
            <CardContent>
              <div className="h-[300px]">
                {loading ? (
                  <Skeleton className="h-full w-full" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={experienceDistribution}
                      margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    >
                      <XAxis
                        dataKey="level"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 12, fill: "currentColor" }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 12, fill: "currentColor" }}
                      />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const d = payload[0].payload
                            return (
                              <div className="rounded-lg border bg-popover px-3 py-2 shadow-md">
                                <p className="font-medium">{d.level}</p>
                                <p className="text-sm text-muted-foreground">
                                  {d.count} job{d.count > 1 ? "s" : ""}
                                </p>
                              </div>
                            )
                          }
                          return null
                        }}
                      />
                      <Bar dataKey="count" fill="hsl(200, 70%, 50%)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Top Hiring Companies</CardTitle></CardHeader>
          <CardContent>
            <div className="h-[500px]">
              {loading ? (
                <Skeleton className="h-full w-full" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topCompanies}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 140, bottom: 5 }}
                  >
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="company"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: "currentColor" }}
                      width={135}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload
                          return (
                            <div className="rounded-lg border bg-popover px-3 py-2 shadow-md">
                              <p className="font-medium">{d.company}</p>
                              <p className="text-sm text-muted-foreground">
                                {d.count} open position{d.count > 1 ? "s" : ""}
                              </p>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <Bar
                      dataKey="count"
                      fill="hsl(142, 71%, 45%)"
                      radius={[0, 4, 4, 0]}
                      maxBarSize={25}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>
      </main>

      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Massar - AI-Powered Job Matching Platform</p>
        </div>
      </footer>
    </div>
  )
}

function KpiCard({
  icon, label, value, tint = "bg-primary/10",
}: {
  icon:  React.ReactNode
  label: string
  value: string | number | null | undefined
  tint?: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <div className={`flex h-12 w-12 items-center justify-center rounded-full ${tint}`}>
          {icon}
        </div>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          {value === null || value === undefined ? (
            <Skeleton className="mt-1 h-7 w-24" />
          ) : (
            <p className="text-2xl font-bold truncate">{value}</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
