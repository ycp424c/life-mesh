import { useState, type FormEvent } from "react"
import { ArrowUpRight, Braces, ShieldAlert } from "lucide-react"
import { toast } from "sonner"

import { SensitivityBadge, StatusBadge } from "@/components/record-badges"
import { PageHeading } from "@/components/page-heading"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { BundleData } from "@/types"

const sourceOptions = [
  { value: "obsidian", label: "Obsidian Vault", detail: "source-backed Markdown" },
  { value: "manual-input", label: "Manual Input", detail: "明确保存的本地记录" },
  { value: "rumor", label: "RumorClaim", detail: "仅作为未核实 lead" },
]

export function BundleView() {
  const [task, setTask] = useState("")
  const [sources, setSources] = useState(["obsidian", "manual-input"])
  const [maxSlices, setMaxSlices] = useState("12")
  const [includeUnverified, setIncludeUnverified] = useState(false)
  const [includeSensitive, setIncludeSensitive] = useState(false)
  const [bundle, setBundle] = useState<BundleData | null>(null)
  const [loading, setLoading] = useState(false)

  function toggleSource(source: string, checked: boolean) {
    setSources((current) => checked ? [...new Set([...current, source])] : current.filter((item) => item !== source))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!task.trim()) return
    setLoading(true)
    setBundle(null)
    try {
      const result = await api<BundleData>("/api/bundles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: task.trim(),
          sources,
          max_slices: Number(maxSlices),
          include_unverified: includeUnverified,
          include_sensitive: includeSensitive,
        }),
      })
      setBundle(result)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="view-enter">
      <PageHeading eyebrow="CONTEXT BUNDLE EXPLORER" title="把问题放进脉络里" description="组装结果只存在于当前响应。Sensitive 默认排除，明确勾选只影响这一次。" aside={<>Artifact, not memory<br />Restricted remains excluded</>} />
      <div className="grid grid-cols-[minmax(300px,.72fr)_minmax(420px,1.28fr)] items-start gap-6 max-xl:grid-cols-1">
        <form onSubmit={submit} className="life-panel sticky top-28 max-xl:static">
          <label htmlFor="bundle-task" className="field-label">Agent 正在处理什么？</label>
          <Textarea id="bundle-task" value={task} onChange={(event) => setTask(event.target.value)} required placeholder="例如：梳理最近关于 LifeMesh Console 的决定和仍未解决的问题" className="min-h-32 resize-y border-paper/10 bg-night-deep/40 text-paper placeholder:text-paper-faint focus-visible:border-amber/50 focus-visible:ring-amber/10" />

          <fieldset className="mt-6"><legend className="field-label">允许来源</legend><div className="grid gap-2">
            {sourceOptions.map((source) => {
              const checked = sources.includes(source.value)
              return <label key={source.value} className="grid grid-cols-[18px_1fr] items-start gap-2.5 rounded-xl border border-paper/10 px-3 py-2.5 text-paper-dim transition hover:bg-paper/[.025]">
                <Checkbox checked={checked} onCheckedChange={(value) => toggleSource(source.value, value === true)} className="mt-0.5 border-paper/25 data-checked:border-amber data-checked:bg-amber data-checked:text-night" />
                <span className="text-xs">{source.label}<small className="mt-0.5 block text-[9px] text-paper-faint">{source.detail}</small></span>
              </label>
            })}
          </div></fieldset>

          <div className="mt-6"><label className="field-label" htmlFor="max-slices">最多 Context Slices</label><Select value={maxSlices} onValueChange={setMaxSlices}><SelectTrigger id="max-slices" className="w-full border-paper/10 bg-night-deep/40 text-paper"><SelectValue /></SelectTrigger><SelectContent className="border-paper/10 bg-moss text-paper"><SelectItem value="8">8 · 聚焦</SelectItem><SelectItem value="12">12 · 平衡</SelectItem><SelectItem value="20">20 · 广泛</SelectItem></SelectContent></Select></div>

          <div className="mt-6 grid gap-2">
            <label className="grid grid-cols-[18px_1fr] items-start gap-2.5 rounded-xl border border-paper/10 px-3 py-2.5 text-paper-dim"><Checkbox checked={includeUnverified} onCheckedChange={(value) => setIncludeUnverified(value === true)} className="mt-0.5 border-paper/25 data-checked:border-unknown data-checked:bg-unknown" /><span className="text-xs">允许未核实线索<small className="mt-0.5 block text-[9px] text-paper-faint">RumorClaim 仍只能作为 lead</small></span></label>
            <label className="grid grid-cols-[18px_1fr] items-start gap-2.5 rounded-xl border border-coral/20 px-3 py-2.5 text-paper-dim"><Checkbox checked={includeSensitive} onCheckedChange={(value) => setIncludeSensitive(value === true)} className="mt-0.5 border-coral/40 data-checked:border-coral data-checked:bg-coral data-checked:text-night" /><span className="text-xs">本次包含 Sensitive<small className="mt-0.5 block text-[9px] text-paper-faint">不记住选择；Restricted 仍排除</small></span></label>
          </div>

          <Button type="submit" disabled={loading || !task.trim() || sources.length === 0} className="mt-6 h-11 w-full border border-amber bg-gradient-to-br from-amber-hot to-amber font-semibold text-night shadow-[0_10px_30px_rgba(242,168,93,.15)] hover:from-amber-hot hover:to-amber-hot hover:shadow-[0_14px_40px_rgba(242,168,93,.23)]">
            {loading ? "正在组装证据脉络…" : "组装 Context Bundle"}<ArrowUpRight />
          </Button>
        </form>

        <section className="life-panel min-h-[520px]">
          {loading ? <div className="grid min-h-[430px] place-content-center justify-items-center gap-4"><div className="seed-loader"><span /></div><p className="font-mono text-[9px] text-paper-faint">ASSEMBLING</p></div> : null}
          {!loading && !bundle ? <div className="bundle-empty"><Braces className="size-14 text-unknown-bright" /><p>输入一个真实任务，查看哪些材料被纳入、哪些被排除，以及为什么。</p></div> : null}
          {!loading && bundle ? <BundleResult bundle={bundle} /> : null}
        </section>
      </div>
    </div>
  )
}

function BundleResult({ bundle }: { bundle: BundleData }) {
  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4 border-b border-paper/10 pb-5"><div><p className="eyebrow">ASSEMBLED ARTIFACT</p><h3 className="mt-1 font-display text-2xl text-paper">{bundle.slices.length} Context Slices</h3></div><SensitivityBadge value={bundle.permission_scope.sensitivity_cap} /></div>
      <div className="grid gap-3">
        {bundle.slices.length ? bundle.slices.map((slice) => (
          <article key={slice.slice_id} className={cn("relative overflow-hidden rounded-2xl border border-paper/10 bg-night-deep/25 py-4 pl-5 pr-4 before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-sprout", slice.evidence_role === "lead" && "before:bg-unknown", slice.evidence_role === "fact" && "before:bg-amber") }>
            <div className="flex flex-wrap gap-2"><StatusBadge value={slice.evidence_role} /><SensitivityBadge value={slice.sensitivity} /><StatusBadge value={String(slice.provenance.source || "source")} /><StatusBadge value={slice.citation_status} /></div>
            <p className="mt-3 whitespace-pre-wrap font-display text-[15px] leading-7 text-paper-dim">{slice.content}</p>
          </article>
        )) : <p className="py-20 text-center text-sm text-paper-faint">没有候选材料通过当前准入边界。</p>}
      </div>
      {bundle.excluded_sources.length ? <div className="mt-6 border-t border-paper/10 pt-5"><h4 className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[.1em] text-paper-faint"><ShieldAlert className="size-3.5" /> Excluded sources · {bundle.excluded_sources.length}</h4><ul className="mt-3 grid gap-1 text-[10px] text-paper-faint">{bundle.excluded_sources.map((item, index) => <li key={`${String(item.source)}:${String(item.reason)}:${index}`}>{String(item.source || "source")} · {String(item.reason || "excluded")}</li>)}</ul></div> : null}
    </div>
  )
}
