import { ChevronRight } from "lucide-react"

import { SensitivityBadge, StatusBadge } from "@/components/record-badges"
import { formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { RecordCard, SelectedRecord } from "@/types"

export function RecordRow({ card, onOpen, compact = false }: { card: RecordCard; onOpen: (record: SelectedRecord) => void; compact?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => onOpen({ domain: card.domain, id: card.id })}
      className={cn(
        "record-render group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-5 rounded-2xl border border-paper/10 bg-moss/45 text-left transition duration-200 hover:-translate-y-px hover:border-amber/20 hover:bg-amber/[.045] focus-visible:border-amber/50 focus-visible:ring-2 focus-visible:ring-amber/20",
        compact ? "px-3 py-3" : "px-5 py-[18px]",
      )}
    >
      <span className="min-w-0">
        <strong className="block truncate text-[13px] font-semibold text-paper">{card.title}</strong>
        <span className="mt-1 block truncate text-[11px] leading-5 text-paper-faint">{card.excerpt || `${card.kind} · ${formatDate(card.timestamp)}`}</span>
      </span>
      <span className="flex flex-wrap items-center justify-end gap-2 max-sm:hidden">
        <StatusBadge value={card.status} />
        <SensitivityBadge value={card.sensitivity} />
        <time className="font-mono text-[8px] text-paper-faint">{formatDate(card.timestamp)}</time>
        <ChevronRight className="size-3.5 text-paper-faint transition-transform group-hover:translate-x-0.5 group-hover:text-amber" />
      </span>
    </button>
  )
}
