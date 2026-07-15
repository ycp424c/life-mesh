import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { DOMAIN_NAMES, sensitivityTone } from "@/lib/format"
import type { RecordCard } from "@/types"

export function DomainBadge({ card }: { card: RecordCard }) {
  const tones = {
    inputs: "border-sprout/25 bg-sprout-deep/45 text-sprout",
    rumors: "border-unknown/30 bg-unknown/10 text-unknown-bright",
    candidates: "border-amber/30 bg-amber/10 text-amber-hot",
  }
  return <Badge variant="outline" className={cn("font-mono text-[9px] uppercase tracking-[.08em]", tones[card.domain])}>{DOMAIN_NAMES[card.domain]}</Badge>
}

export function StatusBadge({ value }: { value: string }) {
  return <Badge variant="outline" className="border-paper/15 bg-paper/5 font-mono text-[9px] text-rational">{value || "unknown"}</Badge>
}

export function SensitivityBadge({ value }: { value: string }) {
  return <Badge variant="outline" className={cn("font-mono text-[9px] uppercase tracking-[.06em]", sensitivityTone(value))}>{value || "Unclassified"}</Badge>
}
