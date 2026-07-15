import { useState, type FormEvent, type ReactNode } from "react"
import {
  Activity,
  Boxes,
  Braces,
  Clock3,
  FileHeart,
  LibraryBig,
  Menu,
  Orbit,
  Search,
  ShieldAlert,
  Sparkles,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type { ViewName } from "@/types"

interface ConsoleShellProps {
  children: ReactNode
  view: ViewName
  onNavigate: (view: ViewName) => void
  onSearch: (query: string) => void
}

const navGroups = [
  {
    label: "观察",
    items: [{ view: "overview" as const, label: "总览工作台", icon: Activity, shortcut: "1" }],
  },
  {
    label: "记录",
    items: [
      { view: "inputs" as const, label: "Manual Inputs", icon: FileHeart, shortcut: "2" },
      { view: "rumors" as const, label: "未知线索", icon: Orbit, shortcut: "3" },
      { view: "candidates" as const, label: "知识候选", icon: Sparkles, shortcut: "4" },
    ],
  },
  {
    label: "知识",
    items: [
      { view: "objects" as const, label: "Canonical Objects", icon: LibraryBig, shortcut: "5" },
      { view: "reviews" as const, label: "Open Reviews", icon: ShieldAlert, shortcut: "6" },
    ],
  },
  {
    label: "探索",
    items: [
      { view: "bundle" as const, label: "Bundle Explorer", icon: Braces, shortcut: "7" },
      { view: "graph" as const, label: "关系图谱", icon: Boxes, shortcut: "8" },
      { view: "timeline" as const, label: "时间脉络", icon: Clock3, shortcut: "9" },
    ],
  },
]

function Navigation({ view, onNavigate, onSelect }: Pick<ConsoleShellProps, "view" | "onNavigate"> & { onSelect?: () => void }) {
  return (
    <nav className="min-h-0 flex-1 overflow-y-auto pr-1" aria-label="主要导航">
      {navGroups.map((group) => (
        <div key={group.label}>
          <p className="mb-1 mt-5 px-3 font-mono text-[9px] font-semibold uppercase tracking-[.17em] text-paper-faint">{group.label}</p>
          {group.items.map((item) => {
            const Icon = item.icon
            return (
              <Tooltip key={item.view}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      onNavigate(item.view)
                      onSelect?.()
                    }}
                    className={cn(
                      "group relative h-10 w-full justify-start gap-3 rounded-xl px-3 text-paper-dim hover:bg-paper/5 hover:text-paper",
                      view === item.view && "border border-amber/20 bg-gradient-to-r from-amber/15 to-sprout/5 text-paper before:absolute before:-left-[19px] before:h-5 before:w-[3px] before:rounded-r before:bg-amber before:shadow-[0_0_18px_rgba(242,168,93,.6)] hover:bg-amber/10",
                    )}
                  >
                    <Icon className={cn("size-4 text-rational", item.view === "rumors" && "text-unknown-bright", item.view === "candidates" && "text-sprout", item.view === "objects" && "text-entity", item.view === "reviews" && "text-coral")} />
                    <span className="flex-1 text-left text-[13px]">{item.label}</span>
                    <kbd className="font-mono text-[9px] font-normal text-paper-faint/60">{item.shortcut}</kbd>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right" className="border-paper/10 bg-moss text-paper">{item.label} · {item.shortcut}</TooltipContent>
              </Tooltip>
            )
          })}
        </div>
      ))}
    </nav>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-3 px-2 pb-4">
      <div className="brand-seed" aria-hidden="true"><span /><span /><span /></div>
      <div>
        <p className="font-mono text-[9px] font-semibold tracking-[.17em] text-paper-faint">PERSONAL CONTEXT</p>
        <h1 className="font-display text-[28px] leading-none tracking-[-.03em] text-paper">LifeMesh</h1>
      </div>
    </div>
  )
}

export function ConsoleShell({ children, view, onNavigate, onSearch }: ConsoleShellProps) {
  const [query, setQuery] = useState("")
  const [mobileOpen, setMobileOpen] = useState(false)

  function submitSearch(event: FormEvent) {
    event.preventDefault()
    const normalized = query.trim()
    if (normalized) onSearch(normalized)
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <div className="ambient ambient-warm" aria-hidden="true" />
      <div className="ambient ambient-unknown" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />

      <aside className="fixed inset-y-0 left-0 z-30 flex w-[248px] flex-col border-r border-paper/10 bg-night-deep/85 px-[18px] py-7 backdrop-blur-2xl max-md:hidden">
        <Brand />
        <Navigation view={view} onNavigate={onNavigate} />
        <div className="mt-4 flex shrink-0 items-center gap-2.5 border-t border-paper/10 px-2 pt-5">
          <span className="session-pulse" aria-hidden="true" />
          <div><strong className="block text-[11px] text-paper-dim">本机只读会话</strong><span className="block font-mono text-[8px] text-paper-faint">127.0.0.1 · 关闭命令即结束</span></div>
        </div>
      </aside>

      <div className="min-w-0 pl-[248px] max-md:pl-0">
        <header className="sticky top-0 z-20 grid min-h-[82px] grid-cols-[minmax(280px,620px)_1fr_auto] items-center gap-5 border-b border-paper/10 bg-night/85 px-[clamp(24px,4vw,58px)] backdrop-blur-2xl max-md:min-h-[70px] max-md:grid-cols-[36px_minmax(0,1fr)_auto] max-md:px-4">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="hidden border-paper/10 bg-paper/[.03] text-paper-dim max-md:inline-flex" aria-label="打开导航"><Menu /></Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[300px] border-paper/10 bg-night-deep p-[18px] text-paper">
              <SheetHeader className="sr-only"><SheetTitle>LifeMesh 导航</SheetTitle></SheetHeader>
              <Brand />
              <Navigation view={view} onNavigate={onNavigate} onSelect={() => setMobileOpen(false)} />
            </SheetContent>
          </Sheet>

          <form onSubmit={submitSearch} className="group grid h-11 grid-cols-[18px_1fr_auto] items-center gap-2.5 rounded-2xl border border-paper/10 bg-paper/[.035] px-3.5 focus-within:border-amber/45 focus-within:bg-paper/[.055] focus-within:shadow-[0_0_0_3px_rgba(242,168,93,.06)] max-md:grid-cols-[18px_1fr]">
            <Search className="size-4 text-paper-faint group-focus-within:text-amber" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              name="query"
              type="search"
              autoComplete="off"
              placeholder="搜索记录、对象、复核项…"
              aria-label="搜索 LifeMesh"
              className="h-auto border-0 bg-transparent px-0 text-paper shadow-none placeholder:text-paper-faint/70 focus-visible:ring-0"
            />
            <span className="font-mono text-[10px] text-paper-faint max-md:hidden">⌘ K</span>
          </form>

          <div />
          <div className="flex items-center gap-3">
            <span className="rounded-full border border-sprout/25 bg-sprout/10 px-2 py-1 font-mono text-[8px] font-semibold tracking-[.08em] text-sprout max-md:hidden">READ ONLY</span>
            <Clock />
          </div>
        </header>

        <main className="min-h-[calc(100vh-82px)] px-[clamp(24px,4vw,58px)] py-[clamp(28px,4vw,58px)] max-md:px-4">{children}</main>
      </div>
    </div>
  )
}

function Clock() {
  const time = new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date())
  return <time className="font-mono text-[11px] text-paper-faint">{time}</time>
}
