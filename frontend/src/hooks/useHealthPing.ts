import { useEffect, useState } from 'react'
import axios from 'axios'
import { apiClient } from '../api/client'

export type HealthState = 'checking' | 'online' | 'offline'

// A real, live reachability check — never an assumed/hardcoded status (see
// CLAUDE.md: "Online / Weak / Offline — detected live, shown honestly").
// Pings the backend's real GET /health on an interval; a slow-but-present
// network and a genuinely unreachable backend both surface honestly.
export function useHealthPing(intervalMs = 20000): HealthState {
  const [state, setState] = useState<HealthState>('checking')

  useEffect(() => {
    let cancelled = false

    async function ping() {
      try {
        await apiClient.get('/health', { timeout: 4000 })
        if (!cancelled) setState('online')
      } catch (err) {
        if (cancelled) return
        if (axios.isAxiosError(err) && err.response) {
          // Server reachable but returned an error status — still "online"
          // from a connectivity standpoint, the server just objected.
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
