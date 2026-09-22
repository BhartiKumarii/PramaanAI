import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { apiClient } from '../api/client'

export type HealthState = 'checking' | 'online' | 'weak' | 'offline'

export interface HealthInfo {
  state: HealthState
  everConnected: boolean
}

export function useHealthPing(intervalMs = 20000): HealthInfo {
  const [state, setState] = useState<HealthState>('checking')
  const everConnected = useRef(false)

  useEffect(() => {
    let cancelled = false
    let attempts = 0

    async function ping() {
      attempts++
      const timeout = attempts <= 3 ? 60000 : 12000
      const start = Date.now()
      try {
        await apiClient.get('/health', { timeout })
        if (cancelled) return
        everConnected.current = true
        const elapsed = Date.now() - start
        setState(elapsed > 5000 ? 'weak' : 'online')
      } catch (err) {
        if (cancelled) return
        if (axios.isAxiosError(err) && err.response) {
          everConnected.current = true
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

  return { state, everConnected: everConnected.current }
}
