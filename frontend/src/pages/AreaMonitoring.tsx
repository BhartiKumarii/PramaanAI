import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
  const navigate = useNavigate()
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
          {rows.map((row) => {
            const total = row.breakdown
              ? row.breakdown.pending + row.breakdown.review_required + row.breakdown.cleared
              : 0
            const hasPending = row.breakdown && (row.breakdown.pending + row.breakdown.review_required) > 0
            return (
              <Card key={row.checkpoint.id}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-accent shrink-0 mt-0.5" />
                    <div>
                      <span className="text-sm font-semibold text-foreground">{row.checkpoint.code}</span>
                      <p className="text-xs text-muted-foreground leading-tight">
                        {row.checkpoint.name}
                        {row.checkpoint.location && ` — ${row.checkpoint.location}`}
                      </p>
                    </div>
                  </div>
                  <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${row.checkpoint.is_active ? 'text-status-clear bg-status-clear-bg' : 'text-status-high bg-status-high-bg'}`}>
                    {row.checkpoint.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <UsersIcon className="h-3.5 w-3.5 shrink-0" />
                    <span>{row.officerCount} officer{row.officerCount !== 1 ? 's' : ''}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <Smartphone className="h-3.5 w-3.5 shrink-0" />
                    <span>{row.deviceCount} device{row.deviceCount !== 1 ? 's' : ''}</span>
                  </div>
                </div>

                {row.breakdown ? (
                  <div className="mt-3 space-y-2 border-t border-border pt-3">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <Radio className="h-3.5 w-3.5" />
                        <span>{total} total screenings</span>
                      </div>
                      {hasPending && (
                        <span className="text-status-review font-medium">
                          {row.breakdown!.pending + row.breakdown!.review_required} need review
                        </span>
                      )}
                    </div>
                    {/* Mini progress bar */}
                    {total > 0 && (
                      <div className="flex h-1.5 overflow-hidden rounded-full bg-secondary">
                        <div className="bg-chart-1 h-full" style={{ width: `${(row.breakdown.pending / total) * 100}%` }} />
                        <div className="bg-status-review h-full" style={{ width: `${(row.breakdown.review_required / total) * 100}%` }} />
                        <div className="bg-status-clear h-full" style={{ width: `${(row.breakdown.cleared / total) * 100}%` }} />
                      </div>
                    )}
                    <div className="flex gap-3 text-xs text-muted-foreground">
                      <span>{row.breakdown.pending} pending</span>
                      <span className="text-status-review">{row.breakdown.review_required} review</span>
                      <span className="text-status-clear">{row.breakdown.cleared} verified</span>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 border-t border-border pt-3 text-xs text-muted-foreground">No screening activity yet.</p>
                )}

                {/* Link to filtered cases */}
                <button
                  onClick={() => navigate(`/console/cases?checkpoint=${row.checkpoint.code}`)}
                  className="mt-3 w-full rounded-md border border-border py-1.5 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
                >
                  View cases at {row.checkpoint.code} →
                </button>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
