import { useEffect, useState } from 'react'
import { FileText, Clock, AlertTriangle, CheckCircle2, Radio, Users as UsersIcon, Server, HardDrive } from 'lucide-react'
import {
  getAdminDashboard,
  getImmigrationDashboard,
  getSupervisorDashboard,
  getSystemHealth,
  listCases,
} from '../api/resources'
import { Card, StatTile } from '../components/StatTile'
import { CaseTable } from '../components/CaseTable'
import { ComprehensiveTestingDashboard } from '../components/ComprehensiveTestingDashboard'
import type {
  AdminDashboard as AdminDashboardData,
  CaseListItem,
  ImmigrationDashboard as ImmigrationDashboardData,
  SupervisorDashboard as SupervisorDashboardData,
  SystemHealth,
} from '../api/types'

// One combined dashboard for every account — see CLAUDE.md: "ship as one
// combined view for now" rather than three hand-built role dashboards.
// Each section below is independently fetched; a section the current
// account's role can't reach (backend RBAC still enforces this, for
// real — see app/core/security.py's require_role) shows an honest "no
// access" note instead of being silently hidden or faked with zeros.
type SectionState<T> = { status: 'loading' | 'ok' | 'forbidden' | 'error'; data: T | null; message?: string }

function useSection<T>(fetcher: () => Promise<T>): SectionState<T> {
  const [state, setState] = useState<SectionState<T>>({ status: 'loading', data: null })

  useEffect(() => {
    let cancelled = false
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: 'ok', data })
      })
      .catch((err) => {
        if (cancelled) return
        if (err?.response?.status === 403) {
          setState({ status: 'forbidden', data: null })
        } else {
          setState({ status: 'error', data: null, message: err?.response?.data?.detail ?? err.message })
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return state
}

function NoAccessNote({ what }: { what: string }) {
  return (
    <p className="text-sm text-muted-foreground">
      Your account doesn't have access to {what}. This section isn't hidden by the frontend — the
      backend rejected the request (403); a different account with the right role would see it here.
    </p>
  )
}

// Hand-rolled progress-bar breakdown — ported from
// sales-ops-dashboard/components/dashboard/charts/pipeline-overview.tsx,
// driven by the real per-checkpoint counts the supervisor dashboard
// endpoint returns (no charting library needed, no fabricated series).
function CheckpointBars({
  rows,
}: {
  rows: { checkpoint_code: string; pending: number; review_required: number; cleared: number }[]
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <div className="space-y-4">
      {rows.map((row, index) => {
        const total = row.pending + row.review_required + row.cleared || 1
        const segments = [
          { key: 'pending', value: row.pending, className: 'bg-chart-1' },
          { key: 'review', value: row.review_required, className: 'bg-status-review' },
          { key: 'cleared', value: row.cleared, className: 'bg-status-clear' },
        ]
        return (
          <div key={row.checkpoint_code}>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="font-medium text-foreground">{row.checkpoint_code}</span>
              <span className="text-xs text-muted-foreground">
                {row.pending} pending · {row.review_required} review · {row.cleared} cleared
              </span>
            </div>
            <div className="flex h-2 overflow-hidden rounded-full bg-secondary">
              {segments.map((seg) => (
                <div
                  key={seg.key}
                  className={`${seg.className} h-full transition-all duration-700 ease-out`}
                  style={{
                    width: mounted ? `${(seg.value / total) * 100}%` : '0%',
                    transitionDelay: `${index * 80}ms`,
                  }}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function Dashboard() {
  const immigration = useSection<ImmigrationDashboardData>(getImmigrationDashboard)
  const supervisor = useSection<SupervisorDashboardData>(getSupervisorDashboard)
  const admin = useSection<AdminDashboardData>(getAdminDashboard)
  const health = useSection<SystemHealth>(getSystemHealth)
  const cases = useSection<CaseListItem[]>(() => listCases({ limit: 20 }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          One combined view of everything — case counts, workload, and system status together.
        </p>
      </div>

      {/* Comprehensive Testing Dashboard */}
      <ComprehensiveTestingDashboard />

      <Card title="Immigration case counts">
        {immigration.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {immigration.status === 'forbidden' && <NoAccessNote what="immigration case counts" />}
        {immigration.status === 'error' && <p className="text-sm text-status-high">{immigration.message}</p>}
        {immigration.status === 'ok' && immigration.data && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="New Cases" value={immigration.data.new_cases} icon={FileText} delay={0} />
            <StatTile
              label="Pending Review"
              value={immigration.data.pending_review}
              accent="review"
              icon={Clock}
              delay={80}
            />
            <StatTile
              label="High Priority"
              value={immigration.data.high_priority}
              accent="high"
              icon={AlertTriangle}
              delay={160}
            />
            <StatTile
              label="Cleared Cases"
              value={immigration.data.cleared_cases}
              accent="clear"
              icon={CheckCircle2}
              delay={240}
            />
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Checkpoint / workload overview" className="lg:col-span-2">
          {supervisor.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
          {supervisor.status === 'forbidden' && <NoAccessNote what="the cross-checkpoint workload overview" />}
          {supervisor.status === 'error' && <p className="text-sm text-status-high">{supervisor.message}</p>}
          {supervisor.status === 'ok' && supervisor.data && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatTile label="Total Scans" value={supervisor.data.total_scans} icon={Radio} />
                <StatTile label="Pending Cases" value={supervisor.data.pending_cases} icon={Clock} />
                <StatTile
                  label="Review Required"
                  value={supervisor.data.review_required}
                  accent="review"
                  icon={AlertTriangle}
                />
                <StatTile label="Active Officers" value={supervisor.data.active_officers} icon={UsersIcon} />
              </div>
              {supervisor.data.checkpoint_breakdown.length > 0 && (
                <div className="border-t border-border pt-4">
                  <CheckpointBars rows={supervisor.data.checkpoint_breakdown} />
                </div>
              )}
            </div>
          )}
        </Card>

        <Card title="System">
          {(admin.status === 'loading' || health.status === 'loading') && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {admin.status === 'forbidden' && <NoAccessNote what="system/admin data" />}
          {admin.status === 'error' && <p className="text-sm text-status-high">{admin.message}</p>}
          {admin.status === 'ok' && admin.data && (
            <div className="space-y-3">
              <StatTile label="Registered Users" value={admin.data.registered_users} icon={UsersIcon} />
              <StatTile label="Registered Devices" value={admin.data.registered_devices} icon={HardDrive} />
              <StatTile label="Sync Queue Pending" value={admin.data.sync_queue_pending} icon={Server} />
            </div>
          )}
          {health.status === 'ok' && health.data && (
            <dl className="mt-4 grid grid-cols-1 gap-3 border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Database</dt>
                <dd
                  className={`text-sm font-medium ${health.data.database_status === 'ok' ? 'text-status-clear' : 'text-status-high'}`}
                >
                  {health.data.database_status}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Analysis Pipeline</dt>
                <dd className="text-sm font-medium text-foreground">{health.data.analysis_pipeline_status}</dd>
              </div>
            </dl>
          )}
        </Card>
      </div>

      <Card title="Recent Cases">
        {cases.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {cases.status === 'forbidden' && <NoAccessNote what="the case queue" />}
        {cases.status === 'error' && <p className="text-sm text-status-high">{cases.message}</p>}
        {cases.status === 'ok' && cases.data && <CaseTable cases={cases.data} />}
      </Card>
    </div>
  )
}
