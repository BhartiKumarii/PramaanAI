import { useEffect, useState } from 'react'
import { listCases } from '../api/resources'
import type { CaseStatus } from '../api/types'

const ALERT_STATUSES: CaseStatus[] = ['REVIEW_REQUIRED']

// A real, polled count — never a hardcoded badge number. Roles that
// can't see cases (e.g. IT_ADMIN) will just get a 403 here and the
// badge silently stays null, matching this app's honest-403 pattern.
export function useAlertsCount(intervalMs = 30000): number | null {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const cases = await listCases({ limit: 100 })
        if (!cancelled) setCount(cases.filter((c) => ALERT_STATUSES.includes(c.status)).length)
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
