import { lazy, Suspense, useEffect, useState } from "react"

import { ConsoleShell } from "@/components/console-shell"
import { LoadingView } from "@/components/loading-view"
import { RecordSheet } from "@/components/record-sheet"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { OverviewView } from "@/views/overview-view"
import { RecordListView } from "@/views/record-list-view"
import { SearchView } from "@/views/search-view"
import { TimelineView } from "@/views/timeline-view"
import type { SelectedRecord, ViewName } from "@/types"

const BundleView = lazy(() => import("@/views/bundle-view").then((module) => ({ default: module.BundleView })))
const GraphView = lazy(() => import("@/views/graph-view").then((module) => ({ default: module.GraphView })))

const shortcutViews: Record<string, ViewName> = {
  "1": "overview",
  "2": "inputs",
  "3": "rumors",
  "4": "candidates",
  "5": "objects",
  "6": "reviews",
  "7": "bundle",
  "8": "graph",
  "9": "timeline",
}

export default function App() {
  const [view, setView] = useState<ViewName>("overview")
  const [searchQuery, setSearchQuery] = useState("")
  const [selected, setSelected] = useState<SelectedRecord | null>(null)

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (event.key === "Escape") setSelected(null)
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        document.querySelector<HTMLInputElement>("input[name='query']")?.focus()
        return
      }
      if (!event.metaKey && !event.ctrlKey && !event.altKey && !target?.matches("input, textarea, select, [contenteditable='true']")) {
        const next = shortcutViews[event.key]
        if (next) setView(next)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  function navigate(next: ViewName) {
    setSelected(null)
    setView(next)
  }

  function search(query: string) {
    setSearchQuery(query)
    setView("search")
  }

  const openRecord = (record: SelectedRecord) => setSelected(record)

  return (
    <TooltipProvider delayDuration={180}>
      <ConsoleShell view={view} onNavigate={navigate} onSearch={search}>
        <Suspense fallback={<LoadingView />}>
          {view === "overview" ? <OverviewView onNavigate={navigate} onOpenRecord={openRecord} /> : null}
          {view === "inputs" || view === "rumors" || view === "candidates" || view === "objects" || view === "reviews" ? <RecordListView key={view} domain={view} onOpenRecord={openRecord} /> : null}
          {view === "bundle" ? <BundleView /> : null}
          {view === "graph" ? <GraphView onOpenRecord={openRecord} /> : null}
          {view === "timeline" ? <TimelineView onOpenRecord={openRecord} /> : null}
          {view === "search" ? <SearchView query={searchQuery} onOpenRecord={openRecord} /> : null}
        </Suspense>
      </ConsoleShell>
      <RecordSheet selected={selected} onClose={() => setSelected(null)} />
      <Toaster richColors theme="dark" position="bottom-right" />
    </TooltipProvider>
  )
}
