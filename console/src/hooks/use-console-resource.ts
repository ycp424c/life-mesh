import { useEffect, useState } from "react"

import { api } from "@/lib/api"

interface ResourceState<T> {
  data: T | null
  error: Error | null
  loading: boolean
}

export function useConsoleResource<T>(path: string | null): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({ data: null, error: null, loading: Boolean(path) })

  useEffect(() => {
    if (!path) {
      setState({ data: null, error: null, loading: false })
      return
    }
    const controller = new AbortController()
    setState({ data: null, error: null, loading: true })
    api<T>(path, { signal: controller.signal })
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return
        setState({ data: null, error: error instanceof Error ? error : new Error(String(error)), loading: false })
      })
    return () => controller.abort()
  }, [path])

  return state
}
