export type Domain = "inputs" | "rumors" | "candidates"
export type ViewName = Domain | "overview" | "bundle" | "graph" | "timeline" | "search"

export interface RecordCard {
  domain: Domain
  id: string
  title: string
  excerpt: string
  status: string
  kind: string
  sensitivity: string
  timestamp: string | null
  tags: string[]
  score?: number
  match_reason?: string
}

export interface HealthItem {
  name: string
  status: string
  detail: string
}

export interface OverviewData {
  generated_at: string
  counts: {
    total: number
    inputs: number
    rumors: number
    candidates: number
    sensitive: number
  }
  queues: {
    manual_active: number
    rumor_review: number
    candidate_review: number
  }
  sensitivity: Record<string, number>
  health: HealthItem[]
  recent: RecordCard[]
}

export interface RecordsData {
  domain: Domain
  items: RecordCard[]
}

export interface SearchData {
  query: string
  results: RecordCard[]
}

export interface RecordDetail {
  card: RecordCard
  data: Record<string, unknown>
}

export interface TimelineData {
  items: RecordCard[]
}

export interface GraphNode {
  id: string
  label: string
  type: string
  status: string
  sensitivity?: string
  domain?: Domain
  record_id?: string
}

export interface GraphEdge {
  source: string
  target: string
  label: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  truth_boundary: string
}

export interface BundleSlice {
  slice_id: string
  evidence_role: string
  provenance: Record<string, unknown>
  citation_status: string
  sensitivity: string
  content: string
}

export interface BundleData {
  bundle_id: string
  permission_scope: {
    allowed_sources: string[]
    sensitivity_cap: string
    include_unverified: boolean
  }
  slices: BundleSlice[]
  excluded_sources: Array<Record<string, unknown>>
  freshness_report: Array<Record<string, unknown>>
  assembly_report: Record<string, unknown>
}

export interface SelectedRecord {
  domain: Domain
  id: string
}
