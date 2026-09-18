import { useEffect, useState } from 'react'
import { MapPin, Radio, Smartphone, Users as UsersIcon } from 'lucide-react'
import { getSupervisorDashboard, listAdminCheckpoints, listAdminDevices, listOfficers } from '../api/resources'
import { Card } from '../components/StatTile'
import type { AdminDevice, Checkpoint, CheckpointBreakdown, Officer } from '../api/types'

interface AreaRow {
  checkpoint: Checkpoint
  breakdown: CheckpointBreakdown | null
  officerCount: number
  deviceCount: number
}

// Composed entirely from data three other real endpoints already expose
// (checkpoints, the supervisor dashboard's per-checkpoint breakdown,
// officers, devices) — no new backend query, just a different join of
// real numbers already fetched elsewhere in this console.
export function AreaMonitoring() {
  const [rows, setRows] = useState<AreaRow[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([listAdminCheckpoints(), getSupervisorDashboard(), listOfficers(), listAdminDevices()])
      .then(([checkpoints, supervisor, officers, devices]) => {
        if (cancelled) return
        const officersByCheckpoint = new Map<string, Officer[]>()
        for (const o of officers) {
          if (!o.checkpoint_code) continue
          const list = officersByCheckpoint.get(o.checkpoint_code) ?? []
          list.push(o)
          officersByCheckpoint.set(o.checkpoint_code, list)
        }
        const officerUsernames = new Set(officers.map((o) => o.username))
        const devicesByCheckpoint = new Map<string, AdminDevice[]>()
        for (const d of devices) {
          if (!d.officer_username || !officerUsernames.has(d.officer_username)) continue
          const owner = officers.find((o) => o.username === d.officer_username)
          if (!owner?.checkpoint_code) continue
          const list = devicesByCheckpoint.get(owner.checkpoint_code) ?? []
          list.push(d)
          devicesByCheckpoint.set(owner.checkpoint_code, list)
        }
        const breakdownByCode = new Map(supervisor.checkpoint_breakdown.map((b) => [b.checkpoint_code, b]))

        setRows(
          checkpoints.map((cp) => ({
            checkpoint: cp,
            breakdown: breakdownByCode.get(cp.code) ?? null,
            officerCount: officersByCheckpoint.get(cp.code)?.length ?? 0,
            deviceCount: devicesByCheckpoint.get(cp.code)?.length ?? 0,
          })),
        )
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail ?? err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Area Monitoring</h1>
        <p className="text-sm text-muted-foreground">
          Live per-checkpoint status — screening activity, officers, and devices registered there.
        </p>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-status-high">{error}</p>}

      {rows && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((row) => (
            <Card key={row.checkpoint.id}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapPin className="h-4.5 w-4.5 text-accent" />
                  <span className="text-sm font-semibold text-foreground">{row.checkpoint.code}</span>
                </div>
                <span className={row.checkpoint.is_active ? 'text-xs text-status-clear' : 'text-xs text-status-high'}>
                  {row.checkpoint.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {row.checkpoint.name}
                {row.checkpoint.location && ` — ${row.checkpoint.location}`}
              </p>

              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs">
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <UsersIcon className="h-3.5 w-3.5" /> {row.officerCount} officers
                </div>
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Smartphone className="h-3.5 w-3.5" /> {row.deviceCount} devices
                </div>
              </div>

              {row.breakdown ? (
                <div className="mt-3 flex items-center gap-3 border-t border-border pt-3 text-xs">
                  <Radio className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-muted-foreground">{row.breakdown.pending} pending</span>
                  <span className="text-status-review">{row.breakdown.review_required} review</span>
                  <span className="text-status-clear">{row.breakdown.cleared} cleared</span>
                </div>
              ) : (
                <p className="mt-3 border-t border-border pt-3 text-xs text-muted-foreground">No screening activity yet.</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
