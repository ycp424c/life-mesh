import { useMemo } from "react"

import { DomainBadge, SensitivityBadge, StatusBadge } from "@/components/record-badges"
import { LoadingView } from "@/components/loading-view"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useConsoleResource } from "@/hooks/use-console-resource"
import { DOMAIN_NAMES, recordContent } from "@/lib/format"
import type { RecordDetail, SelectedRecord } from "@/types"

interface RecordSheetProps {
  selected: SelectedRecord | null
  onClose: () => void
}

const hiddenFields = new Set([
  "text", "claim_text", "summary", "extractions", "embeddings", "derived_objects",
  "audit_events", "candidate_links", "source_envelope", "source_refs_json", "tags_json",
  "statement", "title", "description", "acceptance", "source_links", "review_items",
  "tombstones", "target", "trigger_source",
])

function JsonSection({ title, value }: { title: string; value: unknown }) {
  if (value == null || (Array.isArray(value) && value.length === 0)) return null
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      <pre className="max-h-80 overflow-auto rounded-xl border border-paper/10 bg-night-deep/50 p-3.5 font-mono text-[9px] leading-6 text-rational">{JSON.stringify(value, null, 2)}</pre>
    </section>
  )
}

export function RecordSheet({ selected, onClose }: RecordSheetProps) {
  const path = selected ? `/api/records/${encodeURIComponent(selected.domain)}/${encodeURIComponent(selected.id)}` : null
  const { data, error, loading } = useConsoleResource<RecordDetail>(path)
  const content = data ? recordContent(data.card, data.data) : ""
  const metadata = useMemo(() => {
    if (!data) return []
    return Object.entries(data.data).filter(([, value]) => value !== null && value !== "" && typeof value !== "object").filter(([key]) => !hiddenFields.has(key))
  }, [data])

  return (
    <Sheet open={Boolean(selected)} onOpenChange={(open) => { if (!open) onClose() }}>
      <SheetContent className="w-[min(600px,94vw)] max-w-none gap-0 border-amber/20 bg-night p-0 text-paper shadow-[-30px_0_90px_rgba(0,0,0,.48)]" showCloseButton>
        {loading ? <LoadingView /> : null}
        {error ? <div className="grid min-h-[50vh] place-content-center p-8 text-center text-coral">{error.message}</div> : null}
        {data ? (
          <>
            <SheetHeader className="border-b border-paper/10 bg-night/95 px-7 py-6 backdrop-blur-xl">
              <p className="eyebrow">{DOMAIN_NAMES[data.card.domain]}</p>
              <SheetTitle className="max-w-[480px] font-display text-[28px] leading-tight text-paper">{data.card.title}</SheetTitle>
              <SheetDescription className="sr-only">只读记录详情</SheetDescription>
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1">
              <div className="p-7">
                <div className="mb-6 flex flex-wrap gap-2"><DomainBadge card={data.card} /><StatusBadge value={data.card.status} /><SensitivityBadge value={data.card.sensitivity} /></div>
                {content ? <section className="detail-section"><h3>Content · 原文不遮罩</h3><div className="whitespace-pre-wrap font-display text-[17px] leading-8 text-paper">{content}</div></section> : null}
                {metadata.length ? <section className="detail-section"><h3>Metadata</h3><dl className="grid grid-cols-[minmax(100px,.32fr)_minmax(0,.68fr)] gap-x-4 gap-y-2.5 max-sm:grid-cols-1">{metadata.flatMap(([key, value]) => [<dt key={`${key}-key`} className="font-mono text-[9px] text-paper-faint">{key}</dt>, <dd key={key} className="m-0 break-words text-[11px] leading-6 text-paper-dim">{String(value)}</dd>])}</dl></section> : null}
                <JsonSection title="来源" value={data.data.source_envelope ?? data.data.source_refs} />
                <JsonSection title="Acceptance" value={data.data.acceptance} />
                <JsonSection title="Provenance · 来源链接" value={data.data.source_links} />
                <JsonSection title="触发来源" value={data.data.trigger_source} />
                <JsonSection title="复核目标" value={data.data.target} />
                <JsonSection title="复核历史" value={data.data.review_items} />
                <JsonSection title="Tombstone" value={data.data.tombstones} />
                <JsonSection title="实体提及" value={data.data.entity_mentions} />
                <JsonSection title="关系提及" value={data.data.relation_mentions} />
                <JsonSection title="派生对象" value={data.data.derived_objects ?? data.data.candidate_links} />
                <JsonSection title="Embedding" value={data.data.embeddings} />
                <JsonSection title="审计轨迹" value={data.data.audit_events} />
              </div>
            </ScrollArea>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
