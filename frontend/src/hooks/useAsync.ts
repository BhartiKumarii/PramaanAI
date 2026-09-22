import { useEffect, useState, useCallback } from 'react'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

function isNetworkError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const msg = (err as { message?: string }).message ?? ''
  return msg === 'Network Error' || msg.includes('timeout') || msg.includes('ERR_CONNECTION')
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    async function attempt(retries: number) {
      try {
        const result = await fn()
        if (!cancelled) {
          setData(result)
          setLoading(false)
        }
      } catch (err) {
        if (cancelled) return
        if (isNetworkError(err) && retries < 2) {
          await new Promise((r) => setTimeout(r, (retries + 1) * 2000))
          if (!cancelled) await attempt(retries + 1)
          return
        }
        setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? (err as Error).message ?? 'Request failed')
        setLoading(false)
      }
    }

    attempt(0)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  useEffect(() => load(), [load])

  return { data, loading, error, refetch: () => setTick((t) => t + 1) }
}
