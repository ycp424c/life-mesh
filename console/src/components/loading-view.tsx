import { Skeleton } from "@/components/ui/skeleton"

export function LoadingView() {
  return (
    <div className="grid min-h-[52vh] place-content-center justify-items-center gap-5 text-paper-faint">
      <div className="seed-loader" aria-hidden="true"><span /></div>
      <p className="font-mono text-[10px] uppercase tracking-[.16em]">正在读取本地脉络</p>
      <div className="flex gap-2"><Skeleton className="h-1.5 w-10 bg-paper/10" /><Skeleton className="h-1.5 w-20 bg-paper/10" /></div>
    </div>
  )
}

export function ErrorView({ error }: { error: Error }) {
  return (
    <div className="grid min-h-[52vh] place-content-center gap-3 text-center">
      <p className="font-mono text-[10px] uppercase tracking-[.18em] text-coral">Local read error</p>
      <h2 className="font-display text-3xl text-paper">{error.message}</h2>
      <p className="text-sm text-paper-faint">Console 没有执行任何写操作。请检查本地配置后刷新。</p>
    </div>
  )
}
