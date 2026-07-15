import { ErrorView, LoadingView } from "@/components/loading-view"
import { PageHeading } from "@/components/page-heading"
import { useConsoleResource } from "@/hooks/use-console-resource"
import { DOMAIN_NAMES, formatDate } from "@/lib/format"
import type { SelectedRecord, TimelineData } from "@/types"

export function TimelineView({ onOpenRecord }: { onOpenRecord: (record: SelectedRecord) => void }) {
  const { data, error, loading } = useConsoleResource<TimelineData>("/api/timeline?limit=140")
  if (loading) return <LoadingView />
  if (error) return <ErrorView error={error} />
  if (!data) return null
  return (
    <div className="view-enter">
      <PageHeading eyebrow="TIMELINE" title="记录如何成为时间" description="按发生时间或创建时间排列输入、线索和候选。它显示发生过什么，不替你推断因果。" aside={<>{data.items.length} events<br />newest first</>} />
      <div className="timeline-thread">
        {data.items.map((card) => (
          <button key={`${card.domain}:${card.id}`} type="button" onClick={() => onOpenRecord({ domain: card.domain, id: card.id })} className={`timeline-record timeline-${card.domain}`}>
            <time>{formatDate(card.timestamp)}<br />{DOMAIN_NAMES[card.domain]}</time>
            <span><strong>{card.title}</strong><small>{card.excerpt || card.kind}</small></span>
          </button>
        ))}
      </div>
    </div>
  )
}
