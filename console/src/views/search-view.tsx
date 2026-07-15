import { DomainBadge, SensitivityBadge, StatusBadge } from "@/components/record-badges"
import { ErrorView, LoadingView } from "@/components/loading-view"
import { PageHeading } from "@/components/page-heading"
import { useConsoleResource } from "@/hooks/use-console-resource"
import type { SearchData, SelectedRecord } from "@/types"

export function SearchView({ query, onOpenRecord }: { query: string; onOpenRecord: (record: SelectedRecord) => void }) {
  const { data, error, loading } = useConsoleResource<SearchData>(query ? `/api/search?q=${encodeURIComponent(query)}&limit=40` : null)
  if (loading) return <LoadingView />
  if (error) return <ErrorView error={error} />
  if (!data) return null
  return (
    <div className="view-enter">
      <PageHeading eyebrow="GLOBAL SEARCH" title={`寻找「${data.query}」`} description="跨 Manual Input、RumorClaim 与 Knowledge Candidate 搜索；每条结果保留自己的领域、状态和敏感度。" aside={<>{data.results.length} matches<br />schema stays explicit</>} />
      <div className="grid gap-2.5">
        {data.results.length ? data.results.map((card) => (
          <button key={`${card.domain}:${card.id}`} type="button" onClick={() => onOpenRecord({ domain: card.domain, id: card.id })} className="record-render group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-5 rounded-2xl border border-paper/10 bg-moss/45 px-5 py-[18px] text-left transition hover:-translate-y-px hover:border-amber/20 hover:bg-amber/[.045]">
            <span className="min-w-0"><strong className="block truncate text-[13px] text-paper">{card.title}</strong><span className="mt-1 block truncate text-[11px] text-paper-faint">{card.excerpt || card.match_reason}</span></span>
            <span className="flex flex-wrap justify-end gap-2 max-sm:hidden"><DomainBadge card={card} /><StatusBadge value={card.status} /><SensitivityBadge value={card.sensitivity} /></span>
          </button>
        )) : <p className="py-24 text-center text-sm text-paper-faint">没有找到匹配记录。</p>}
      </div>
    </div>
  )
}
