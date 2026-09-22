import { useEffect, useState } from 'react'
import { listCases } from '../api/resources'
import type { CaseStatus } from '../api/types'

const AWAITING_STATUSES: CaseStatus[] = ['SENT', 'REVIEW_REQUIRED']

export function useAlertsCount(intervalMs = 30000): number | null {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const cases = await listCases({ limit: 200 })
        if (!cancelled) setCount(cases.filter((c) => AWAITING_STATUSES.includes(c.status)).length)
      } catch {
        if (!cancelled) setCount(null)
      }
    }

    poll()
    const id = setInterval(poll, intervalMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [intervalMs])

  return count
}
