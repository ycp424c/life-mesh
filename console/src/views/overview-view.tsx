import { ArrowUpRight } from "lucide-react"

import { ErrorView, LoadingView } from "@/components/loading-view"
import { RecordRow } from "@/components/record-row"
import { Button } from "@/components/ui/button"
import { useConsoleResource } from "@/hooks/use-console-resource"
import { cn } from "@/lib/utils"
import type { OverviewData, SelectedRecord, ViewName } from "@/types"

interface OverviewViewProps {
  onNavigate: (view: ViewName) => void
  onOpenRecord: (record: SelectedRecord) => void
}

export function OverviewView({ onNavigate, onOpenRecord }: OverviewViewProps) {
  const { data, error, loading } = useConsoleResource<OverviewData>("/api/overview")
  if (loading) return <LoadingView />
  if (error) return <ErrorView error={error} />
  if (!data) return null

  const metrics = [
    ["可见记录", data.counts.total, "live local state"],
    ["明确输入", data.counts.inputs, "manual traces"],
    ["未知线索", data.counts.rumors, "unverified"],
    ["知识候选", data.counts.candidates, "awaiting review"],
    ["敏感内容", data.counts.sensitive, "visible · labeled"],
  ] as const

  return (
    <div className="view-enter">
      <section className="hero-stage">
        <div className="relative z-10 flex flex-col items-start justify-center px-[clamp(32px,5vw,68px)] py-12">
          <p className="eyebrow">LOCAL CONTEXT · LIVE</p>
          <h2 className="mt-4 max-w-3xl font-display text-[clamp(42px,5.4vw,78px)] leading-[.98] tracking-[-.045em] text-paper">
            生命不是仓库，<br />是一张有<span className="italic text-amber-hot">温度</span>的证据网。
          </h2>
          <p className="mt-6 max-w-xl text-sm leading-7 text-paper-dim">把已知放在光里，让未知保留边界。这里读取真实的本地状态，但不替你改写任何一条记录。</p>
        </div>
        <div className="relative min-h-[330px] max-md:min-h-[240px]" aria-hidden="true">
          <div className="life-orbit"><i /><i /><i /></div>
          <span className="absolute bottom-6 right-6 max-w-44 font-mono text-[9px] uppercase leading-4 tracking-[.08em] text-paper-faint">warmth / growth / unknown / reason</span>
        </div>
      </section>

      <section className="metric-strand" aria-label="数据概览">
        {metrics.map(([label, value, detail], index) => (
          <article key={label} className={cn("metric-cell", index === 1 && "[&_strong]:text-amber-hot", index === 2 && "[&_strong]:text-unknown-bright", index === 3 && "[&_strong]:text-sprout", index === 4 && "[&_strong]:text-coral")}>
            <span>{label}</span><strong>{value}</strong><small>{detail}</small>
          </article>
        ))}
      </section>

      <section className="grid grid-cols-[minmax(0,1.25fr)_minmax(320px,.75fr)] gap-6 max-xl:grid-cols-1">
        <article className="life-panel">
          <header className="mb-5 flex items-center justify-between gap-4">
            <h3 className="font-display text-[21px] text-paper">最近浮现</h3>
            <Button variant="ghost" size="sm" onClick={() => onNavigate("timeline")} className="font-mono text-[9px] uppercase tracking-[.07em] text-amber hover:bg-amber/10 hover:text-amber-hot">沿时间查看 <ArrowUpRight /></Button>
          </header>
          <div className="grid gap-2.5">
            {data.recent.length ? data.recent.map((card) => <RecordRow key={`${card.domain}:${card.id}`} card={card} onOpen={onOpenRecord} compact />) : <p className="py-16 text-center text-sm text-paper-faint">本地还没有记录。Console 会在数据出现后自然生长。</p>}
          </div>
        </article>

        <article className="life-panel">
          <header className="mb-4 flex items-center justify-between gap-4"><h3 className="font-display text-[21px] text-paper">系统生命体征</h3><span className="eyebrow">NO NETWORK PROBE</span></header>
          <div>
            {data.health.map((item) => (
              <div key={item.name} className="grid grid-cols-[9px_1fr_auto] items-center gap-3 border-b border-paper/10 py-3 last:border-0">
                <i className={cn("size-[7px] rounded-full bg-sprout shadow-[0_0_14px_rgba(168,204,114,.45)]", ["missing", "degraded", "unknown"].includes(item.status) && "bg-coral shadow-[0_0_14px_rgba(229,131,103,.4)]", ["not configured", "optional / offline"].includes(item.status) && "border border-paper-faint bg-transparent shadow-none")} />
                <div><strong className="block text-xs text-paper">{item.name}</strong><span className="font-mono text-[9px] uppercase tracking-[.05em] text-paper-faint">{item.detail}</span></div>
                <span className="text-right font-mono text-[8px] text-paper-faint">{item.status}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 grid grid-cols-3 overflow-hidden rounded-2xl border border-paper/10 max-sm:grid-cols-1">
            {[["活动输入", data.queues.manual_active], ["线索复核", data.queues.rumor_review], ["候选复核", data.queues.candidate_review]].map(([label, value]) => (
              <div key={label} className="border-r border-paper/10 p-4 last:border-0 max-sm:border-b max-sm:border-r-0"><span className="font-mono text-[8px] uppercase text-paper-faint">{label}</span><strong className="mt-1 block font-display text-3xl font-medium text-paper">{value}</strong></div>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}
