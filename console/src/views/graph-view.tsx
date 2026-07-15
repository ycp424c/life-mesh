import { useMemo } from "react"

import { ErrorView, LoadingView } from "@/components/loading-view"
import { PageHeading } from "@/components/page-heading"
import { useConsoleResource } from "@/hooks/use-console-resource"
import type { GraphData, GraphNode, SelectedRecord } from "@/types"

const width = 1200
const height = 650
const centers: Record<string, [number, number]> = {
  input: [250, 250], tag: [210, 475], rumor: [565, 175], relation: [780, 110],
  entity: [810, 320], candidate: [560, 480], object: [800, 505], source: [1010, 390],
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.max(minimum, Math.min(maximum, value))
}

function nodePositions(nodes: GraphNode[]) {
  const groups = new Map<string, GraphNode[]>()
  nodes.forEach((node) => groups.set(node.type, [...(groups.get(node.type) || []), node]))
  const positions = new Map<string, { x: number; y: number }>()
  groups.forEach((items, type) => {
    const [cx, cy] = centers[type] || [width / 2, height / 2]
    const radius = Math.min(92 + items.length * 3, 150)
    items.forEach((node, index) => {
      const angle = index * 2.399963 + type.length * 0.47
      const distance = items.length === 1 ? 0 : radius * (0.28 + 0.72 * Math.sqrt((index + 1) / items.length))
      positions.set(node.id, { x: clamp(cx + Math.cos(angle) * distance, 34, width - 150), y: clamp(cy + Math.sin(angle) * distance, 60, height - 50) })
    })
  })
  return positions
}

export function GraphView({ onOpenRecord }: { onOpenRecord: (record: SelectedRecord) => void }) {
  const { data, error, loading } = useConsoleResource<GraphData>("/api/graph?limit=40")
  const positions = useMemo(() => data ? nodePositions(data.nodes) : new Map(), [data])
  if (loading) return <LoadingView />
  if (error) return <ErrorView error={error} />
  if (!data) return null

  return (
    <div className="view-enter">
      <PageHeading eyebrow="KNOWLEDGE GRAPH" title="真实关系，不补造连线" description="只展示已存储的标签、entity/relation mention、promotion link 与 source reference。孤立节点也是诚实的结果。" aside={<>{data.nodes.length} nodes<br />{data.edges.length} stored edges</>} />
      <div className="graph-shell">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="LifeMesh 真实关系图谱" className="h-full min-h-[650px] w-full max-md:min-h-[520px]">
          <g aria-hidden="true">
            {data.edges.map((edge) => {
              const source = positions.get(edge.source)
              const target = positions.get(edge.target)
              if (!source || !target) return null
              const curve = Math.max(Math.abs(target.x - source.x) * 0.24, 22)
              return <path key={`${edge.source}:${edge.target}:${edge.label}`} className="graph-edge" d={`M ${source.x} ${source.y} C ${source.x + curve} ${source.y}, ${target.x - curve} ${target.y}, ${target.x} ${target.y}`}><title>{edge.label}</title></path>
            })}
          </g>
          <g>
            {data.nodes.map((node) => {
              const point = positions.get(node.id)
              if (!point) return null
              const interactive = Boolean(node.domain && node.record_id)
              return <g key={node.id} className={`graph-node graph-${node.type}`} transform={`translate(${point.x} ${point.y})`} role={interactive ? "button" : "img"} tabIndex={interactive ? 0 : -1} onClick={() => { if (node.domain && node.record_id) onOpenRecord({ domain: node.domain, id: node.record_id }) }} onKeyDown={(event) => { if ((event.key === "Enter" || event.key === " ") && node.domain && node.record_id) onOpenRecord({ domain: node.domain, id: node.record_id }) }}>
                <circle r={node.type === "entity" ? 7 : 5} /><text x="11" y="3">{node.label.length > 24 ? `${node.label.slice(0, 23)}…` : node.label}</text><title>{node.label} · {node.type}</title>
              </g>
            })}
          </g>
        </svg>
        <p className="absolute left-5 top-5 max-w-sm border-l-2 border-unknown bg-night-deep/65 px-3 py-2 font-mono text-[8px] uppercase leading-4 tracking-[.06em] text-paper-faint">TRUTH BOUNDARY · {data.truth_boundary}</p>
        <div className="absolute bottom-4 right-4 flex max-w-[70%] flex-wrap gap-3 rounded-full border border-paper/10 bg-night-deep/80 px-3 py-2 font-mono text-[8px] text-paper-faint backdrop-blur-xl"><span className="text-sprout">● 输入</span><span className="text-unknown-bright">● 未知</span><span className="text-amber">● 候选</span><span className="text-entity">● 实体</span><span className="text-rational">● 来源</span></div>
      </div>
    </div>
  )
}
