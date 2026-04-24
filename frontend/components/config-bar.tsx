"use client"

import { useState, useCallback } from "react"
import { X, Plus, Search } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"

interface ConfigBarProps {
  skills: string[]
  onSkillsChange: (skills: string[]) => void
  onSearch: (config: SearchConfig) => void
}

export interface SearchConfig {
  skills: string[]
  experience: number
  seniority: string
  searchQuery: string
}

const availableSkills = [
  "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "Python",
  "AWS", "Docker", "Kubernetes", "PostgreSQL", "MongoDB", "GraphQL",
  "REST APIs", "Git", "CI/CD", "Agile", "TDD", "CSS", "HTML", "SQL",
  "Redis", "Linux", "Terraform", "Java", "Go", "Rust", "Vue.js", "Angular",
  "Swift", "Kotlin", "Flutter", "React Native", "Machine Learning", "Data Science"
]

export function ConfigBar({ skills, onSkillsChange, onSearch }: ConfigBarProps) {
  const [experience, setExperience] = useState(3)
  const [seniority, setSeniority] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [skillInput, setSkillInput] = useState("")
  const [showSuggestions, setShowSuggestions] = useState(false)

  const removeSkill = useCallback((skillToRemove: string) => {
    onSkillsChange(skills.filter(s => s !== skillToRemove))
  }, [skills, onSkillsChange])

  const addSkill = useCallback((skill: string) => {
    if (!skills.includes(skill)) {
      onSkillsChange([...skills, skill])
    }
    setSkillInput("")
    setShowSuggestions(false)
  }, [skills, onSkillsChange])

  const filteredSuggestions = availableSkills.filter(
    s => s.toLowerCase().includes(skillInput.toLowerCase()) && !skills.includes(s)
  ).slice(0, 5)

  const handleSearch = useCallback(() => {
    onSearch({
      skills,
      experience,
      seniority,
      searchQuery
    })
  }, [skills, experience, seniority, searchQuery, onSearch])

  return (
    <Card className="border-border/50 bg-card/80 backdrop-blur">
      <CardContent className="p-6">
        <div className="flex flex-col gap-6">
          {/* Skills Section */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Detected Skills</Label>
            <div className="flex flex-wrap gap-2">
              {skills.map((skill) => (
                <Badge
                  key={skill}
                  variant="secondary"
                  className="bg-primary/10 text-primary hover:bg-primary/20 pr-1"
                >
                  {skill}
                  <button
                    onClick={() => removeSkill(skill)}
                    className="ml-1 rounded-full p-0.5 hover:bg-primary/20"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              <div className="relative">
                <div className="flex items-center gap-1">
                  <Input
                    value={skillInput}
                    onChange={(e) => {
                      setSkillInput(e.target.value)
                      setShowSuggestions(true)
                    }}
                    onFocus={() => setShowSuggestions(true)}
                    placeholder="Add skill..."
                    className="h-7 w-32 text-sm"
                  />
                  {skillInput && (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => addSkill(skillInput)}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                {showSuggestions && skillInput && filteredSuggestions.length > 0 && (
                  <div className="absolute top-full left-0 z-10 mt-1 w-48 rounded-md border bg-popover p-1 shadow-md">
                    {filteredSuggestions.map((skill) => (
                      <button
                        key={skill}
                        className="w-full rounded px-2 py-1.5 text-left text-sm hover:bg-accent"
                        onClick={() => addSkill(skill)}
                      >
                        {skill}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Filters Row */}
          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="experience" className="text-sm font-medium">
                Experience (years)
              </Label>
              <Input
                id="experience"
                type="number"
                min={0}
                max={30}
                value={experience}
                onChange={(e) => setExperience(Number(e.target.value))}
                className="h-10"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Seniority</Label>
              <Select value={seniority} onValueChange={setSeniority}>
                <SelectTrigger className="h-10">
                  <SelectValue placeholder="Select level" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Levels</SelectItem>
                  <SelectItem value="entry">Entry</SelectItem>
                  <SelectItem value="junior">Junior</SelectItem>
                  <SelectItem value="mid">Mid</SelectItem>
                  <SelectItem value="senior">Senior</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="search" className="text-sm font-medium">
                Search by title/company
              </Label>
              <Input
                id="search"
                placeholder="e.g. Frontend, Google..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-10"
              />
            </div>

            <div className="flex items-end">
              <Button
                onClick={handleSearch}
                className="h-10 w-full bg-primary hover:bg-primary/90"
              >
                <Search className="mr-2 h-4 w-4" />
                Find Matches
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
