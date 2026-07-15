import type { ReactNode } from "react"

interface PageHeadingProps {
  eyebrow: string
  title: string
  description: string
  aside?: ReactNode
}

export function PageHeading({ eyebrow, title, description, aside }: PageHeadingProps) {
  return (
    <header className="mb-8 flex items-end justify-between gap-8 max-md:block">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="mt-2 font-display text-5xl leading-none tracking-[-.035em] text-paper max-md:text-4xl">{title}</h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-paper-faint">{description}</p>
      </div>
      {aside ? <div className="shrink-0 text-right font-mono text-[10px] leading-5 text-paper-faint max-md:mt-4 max-md:text-left">{aside}</div> : null}
    </header>
  )
}
