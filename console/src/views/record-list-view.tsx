import { useMemo, useState } from "react"

import { ErrorView, LoadingView } from "@/components/loading-view"
import { PageHeading } from "@/components/page-heading"
import { RecordRow } from "@/components/record-row"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useConsoleResource } from "@/hooks/use-console-resource"
import type { Domain, RecordsData, SelectedRecord } from "@/types"

const copy = {
  inputs: { eyebrow: "MANUAL INPUTS", title: "被你明确留下的痕迹", description: "截图、活动、心情、任务与短记。Sensitive 正文保持直接可见，敏感度标签始终在场。" },
  rumors: { eyebrow: "UNKNOWN / UNVERIFIED", title: "让未知保持未知", description: "这里保存值得复核、但尚不足以成为事实的线索。紫色意味着边界，而不是结论。" },
  candidates: { eyebrow: "KNOWLEDGE CANDIDATES", title: "正在形成的知识", description: "候选不是事实。它们保留来源、置信度与风险，等待未来统一写模型中的正式确认。" },
  objects: { eyebrow: "CANONICAL OBJECTS", title: "被确认的长期对象", description: "Fact、Memory、Task 与 Event 共用统一接受路径。每个对象仍保留敏感度、来源和生命周期。" },
  reviews: { eyebrow: "OPEN REVIEWS", title: "来源断裂，需要你看一眼", description: "这里只显示尚未关闭的复核项，并把触发来源与目标对象并排呈现；Console 不在这里替你处理。" },
} satisfies Record<Domain, { eyebrow: string; title: string; description: string }>

export function RecordListView({ domain, onOpenRecord }: { domain: Domain; onOpenRecord: (record: SelectedRecord) => void }) {
  const [filter, setFilter] = useState("all")
  const { data, error, loading } = useConsoleResource<RecordsData>(`/api/records?domain=${domain}&limit=120`)
  const statuses = useMemo(() => data ? [...new Set(data.items.map((item) => item.status))].sort() : [], [data])
  const filtered = useMemo(() => data?.items.filter((item) => filter === "all" || item.status === filter) ?? [], [data, filter])
  if (loading) return <LoadingView />
  if (error) return <ErrorView error={error} />
  if (!data) return null
  const heading = copy[domain]

  return (
    <div className="view-enter">
      <PageHeading eyebrow={heading.eyebrow} title={heading.title} description={heading.description} aside={<>{data.items.length} records<br />read-only view</>} />
      <Tabs value={filter} onValueChange={setFilter} className="gap-4">
        <TabsList className="h-auto flex-wrap justify-start rounded-full border border-paper/10 bg-paper/[.025] p-1">
          <TabsTrigger value="all" className="rounded-full px-3 font-mono text-[9px] data-active:bg-sprout/10 data-active:text-sprout">全部</TabsTrigger>
          {statuses.map((status) => <TabsTrigger key={status} value={status} className="rounded-full px-3 font-mono text-[9px] data-active:bg-sprout/10 data-active:text-sprout">{status}</TabsTrigger>)}
        </TabsList>
      </Tabs>
      <div className="mt-4 grid gap-2.5">
        {filtered.length ? filtered.map((card) => <RecordRow key={card.id} card={card} onOpen={onOpenRecord} />) : <p className="py-24 text-center text-sm text-paper-faint">这个状态下还没有记录。</p>}
      </div>
    </div>
  )
}
