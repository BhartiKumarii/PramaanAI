import { useEffect, useState } from 'react'
import axios from 'axios'
import { apiClient } from '../api/client'

export type HealthState = 'checking' | 'online' | 'weak' | 'offline'

// A real, live reachability check — never an assumed/hardcoded status (see
// CLAUDE.md: "Online / Weak / Offline — detected live, shown honestly").
// Pings the backend's real GET /health on an interval; a slow-but-present
// network and a genuinely unreachable backend both surface honestly.
// Uses a long first-ping timeout (45s) to survive Render free-tier cold
// starts, then a shorter timeout for subsequent pings.
export function useHealthPing(intervalMs = 20000): HealthState {
  const [state, setState] = useState<HealthState>('checking')

  useEffect(() => {
    let cancelled = false
    let firstPing = true

    async function ping() {
      const timeout = firstPing ? 45000 : 10000
      firstPing = false
      const start = Date.now()
      try {
        await apiClient.get('/health', { timeout })
        if (cancelled) return
        const elapsed = Date.now() - start
        setState(elapsed > 5000 ? 'weak' : 'online')
      } catch (err) {
        if (cancelled) return
        if (axios.isAxiosError(err) && err.response) {
          setState('online')
        } else {
          setState('offline')
        }
      }
    }

    ping()
    const id = setInterval(ping, intervalMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [intervalMs])

  return state
}
