import { Brain, Sparkles, Building2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

const features = [
  {
    icon: Brain,
    title: "AI Semantic Matching",
    description: "Deep learning algorithms understand your skills contextually"
  },
  {
    icon: Sparkles,
    title: "100+ Skill Patterns",
    description: "Comprehensive skill taxonomy for accurate matching"
  },
  {
    icon: Building2,
    title: "Real Job Listings",
    description: "Live opportunities from top tech companies in Riyadh"
  }
]

export function FeatureCards() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {features.map((feature) => (
        <Card key={feature.title} className="border-border/50 bg-card/50 backdrop-blur">
          <CardContent className="flex flex-col items-center p-6 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <feature.icon className="h-6 w-6 text-primary" />
            </div>
            <h3 className="mb-2 font-semibold">{feature.title}</h3>
            <p className="text-sm text-muted-foreground">{feature.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
