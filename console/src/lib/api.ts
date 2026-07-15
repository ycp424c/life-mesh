export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
  })
  const payload = (await response.json().catch(() => ({ error: "无法解析本机响应" }))) as T & {
    error?: string
  }
  if (!response.ok) {
    throw new ApiError(payload.error || `请求失败 (${response.status})`, response.status)
  }
  return payload
}
