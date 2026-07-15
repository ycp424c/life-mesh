import type { Domain, RecordCard } from "@/types"

export const DOMAIN_NAMES: Record<Domain, string> = {
  inputs: "Manual Input",
  rumors: "未知线索",
  candidates: "知识候选",
}

export function formatDate(value: string | null, withTime = true): string {
  if (!value) return "时间未记录"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : { year: "numeric" }),
  }).format(date)
}

export function sensitivityTone(value: string): string {
  if (["Sensitive", "Restricted"].includes(value)) return "border-coral/35 bg-coral/10 text-coral"
  if (["Public", "Internal"].includes(value)) return "border-sprout/30 bg-sprout/10 text-sprout"
  return "border-paper/15 bg-paper/5 text-paper-dim"
}

export function recordContent(card: RecordCard, data: Record<string, unknown>): string {
  if (card.domain === "inputs") {
    const extractions = Array.isArray(data.extractions)
      ? data.extractions.flatMap((item) => {
          if (!item || typeof item !== "object") return []
          const text = (item as Record<string, unknown>).text
          return typeof text === "string" ? [text] : []
        })
      : []
    return [data.text, ...extractions].filter((item): item is string => typeof item === "string" && Boolean(item)).join("\n\n")
  }
  if (card.domain === "rumors") return typeof data.claim_text === "string" ? data.claim_text : ""
  return typeof data.summary === "string" ? data.summary : ""
}
