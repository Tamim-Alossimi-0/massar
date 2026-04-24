"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Moon, Sun, Briefcase } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function Header() {
  const { theme, setTheme } = useTheme()
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Briefcase className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="text-xl font-bold">Massar</span>
        </Link>

        <nav className="flex items-center gap-1">
          <Link href="/">
            <Button
              variant="ghost"
              className={cn(
                "text-sm font-medium transition-colors",
                pathname === "/" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              Job Matcher
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button
              variant="ghost"
              className={cn(
                "text-sm font-medium transition-colors",
                pathname === "/dashboard" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              Market Dashboard
            </Button>
          </Link>
        </nav>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>
      </div>
    </header>
  )
}
