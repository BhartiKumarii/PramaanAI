import { useEffect, useState } from 'react'
import { FileText, Clock, AlertTriangle, CheckCircle2, Radio, Users as UsersIcon, Server, HardDrive } from 'lucide-react'
import {
  getAdminDashboard,
  getAnalyticsDashboard,
  getImmigrationDashboard,
  getSupervisorDashboard,
  getSystemHealth,
  listCases,
} from '../api/resources'
import { Card, StatTile } from '../components/StatTile'
import { CaseTable } from '../components/CaseTable'
import type {
  AdminDashboard as AdminDashboardData,
  AnalyticsDashboard,
  CaseListItem,
  ImmigrationDashboard as ImmigrationDashboardData,
  SupervisorDashboard as SupervisorDashboardData,
  SystemHealth,
} from '../api/types'

type SectionState<T> = { status: 'loading' | 'ok' | 'forbidden' | 'error'; data: T | null; message?: string }

function useSection<T>(fetcher: () => Promise<T>): SectionState<T> {
  const [state, setState] = useState<SectionState<T>>({ status: 'loading', data: null })
  useEffect(() => {
    let cancelled = false
    fetcher()
      .then((data) => { if (!cancelled) setState({ status: 'ok', data }) })
      .catch((err) => {
        if (cancelled) return
        if (err?.response?.status === 403) setState({ status: 'forbidden', data: null })
        else setState({ status: 'error', data: null, message: err?.response?.data?.detail ?? err.message })
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return state
}

function NoAccessNote({ what }: { what: string }) {
  return (
    <p className="text-sm text-muted-foreground">
      Your account doesn't have access to {what}. The backend rejected the request (403).
    </p>
  )
}

// ── Donut chart ─────────────────────────────────────────────────────────────

interface DonutSlice { value: number; color: string; label: string }

function DonutChart({ slices, size = 120 }: { slices: DonutSlice[]; size?: number }) {
  const total = slices.reduce((s, d) => s + d.value, 0) || 1
  const r = 40
  const cx = size / 2
  const cy = size / 2
  const strokeWidth = 14

  let offset = -90 // start at top
  const arcs = slices.map((s) => {
    const pct = s.value / total
    const startAngle = offset
    offset += pct * 360
    return { ...s, pct, startAngle, endAngle: offset }
  })

  function polarToXY(angle: number, radius: number) {
    const rad = (angle * Math.PI) / 180
    return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) }
  }

  function arcPath(startAngle: number, endAngle: number) {
    const gap = 1.5
    const sa = startAngle + gap / 2
    const ea = endAngle - gap / 2
    if (ea - sa <= 0) return ''
    const large = ea - sa > 180 ? 1 : 0
    const s = polarToXY(sa, r)
    const e = polarToXY(ea, r)
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`
  }

  const topSlice = [...slices].sort((a, b) => b.value - a.value)[0]

  return (
    <div className="flex items-center gap-6">
      <svg width={size} height={size} aria-hidden="true">
        {/* Background ring */}
        <circle cx={cx} cy={cy} r={r} fill="none" strokeWidth={strokeWidth} stroke="hsl(var(--secondary))" />
        {arcs.map((arc) => (
          arc.value > 0 && (
            <path
              key={arc.label}
              d={arcPath(arc.startAngle, arc.endAngle)}
              fill="none"
              stroke={arc.color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
            />
          )
        ))}
        {/* Centre label */}
        <text x={cx} y={cy - 6} textAnchor="middle" className="fill-foreground" style={{ fontSize: 18, fontWeight: 700 }}>
          {total}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className="fill-muted-foreground" style={{ fontSize: 9 }}>
          total
        </text>
      </svg>
      <ul className="space-y-2 text-sm">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} aria-hidden="true" />
            <span className="text-muted-foreground">{s.label}</span>
            <span className="ml-auto font-semibold text-foreground">{s.value}</span>
            <span className="w-10 text-right text-xs text-muted-foreground">
              {total > 0 ? Math.round((s.value / total) * 100) : 0}%
            </span>
          </li>
        ))}
        {topSlice && total > 0 && (
          <li className="border-t border-border pt-2 text-xs text-muted-foreground">
            Largest: <span className="font-medium text-foreground">{topSlice.label}</span>
          </li>
        )}
      </ul>
    </div>
  )
}

// ── Daily bar chart ──────────────────────────────────────────────────────────

function DailyBars({ buckets }: { buckets: { key: string; count: number }[] }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true))
    return () => cancelAnimationFrame(id)
  }, [])

  const recent = buckets.slice(-10)
  const max = Math.max(...recent.map((b) => b.count), 1)

  return (
    <div className="space-y-1">
      <div className="flex h-28 items-end gap-1">
        {recent.map((b, i) => (
          <div key={b.key} className="group relative flex flex-1 flex-col items-center gap-1">
            <div className="relative w-full flex-1 flex items-end">
              <div
                className="w-full rounded-t bg-accent transition-all duration-500 ease-out"
                style={{
                  height: mounted ? `${(b.count / max) * 100}%` : '0%',
                  transitionDelay: `${i * 30}ms`,
                  minHeight: b.count > 0 ? 4 : 0,
                }}
              />
            </div>
            {/* Tooltip on hover */}
            <span className="pointer-events-none absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-card border border-border px-1.5 py-0.5 text-xs opacity-0 shadow group-hover:opacity-100 transition-opacity z-10">
              {b.count} · {b.key}
            </span>
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{recent[0]?.key ?? ''}</span>
        <span>{recent[recent.length - 1]?.key ?? ''}</span>
      </div>
    </div>
  )
}

// ── Checkpoint progress bars ─────────────────────────────────────────────────

function CheckpointBars({ rows }: {
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
          { key: 'pending', value: row.pending, label: 'Pending', className: 'bg-chart-1' },
          { key: 'review', value: row.review_required, label: 'Review', className: 'bg-status-review' },
          { key: 'cleared', value: row.cleared, label: 'Verified', className: 'bg-status-clear' },
        ]
        return (
          <div key={row.checkpoint_code}>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="font-medium text-foreground">{row.checkpoint_code}</span>
              <span className="flex gap-2 text-xs text-muted-foreground">
                {segments.map((s) => (
                  <span key={s.key} className="flex items-center gap-1">
                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${s.className}`} />
                    {s.value} {s.label}
                  </span>
                ))}
              </span>
            </div>
            <div className="flex h-2.5 overflow-hidden rounded-full bg-secondary">
              {segments.map((seg) => (
                <div
                  key={seg.key}
                  title={`${seg.label}: ${seg.value}`}
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

// ── Main component ───────────────────────────────────────────────────────────

export function Dashboard() {
  const immigration = useSection<ImmigrationDashboardData>(getImmigrationDashboard)
  const supervisor = useSection<SupervisorDashboardData>(getSupervisorDashboard)
  const admin = useSection<AdminDashboardData>(getAdminDashboard)
  const health = useSection<SystemHealth>(getSystemHealth)
  const analytics = useSection<AnalyticsDashboard>(() => getAnalyticsDashboard(14))
  const cases = useSection<CaseListItem[]>(() => listCases({ limit: 10 }))

  // Build risk donut slices from analytics
  const riskSlices: DonutSlice[] = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_risk_level.map((b) => ({
        label: b.key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        value: b.count,
        color: b.key === 'HIGH_RISK'
          ? 'hsl(var(--status-high))'
          : b.key === 'MEDIUM_RISK'
            ? 'hsl(var(--status-review))'
            : 'hsl(var(--status-clear))',
      }))
    : []

  // Build decision donut slices
  const decisionSlices: DonutSlice[] = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_decision
        .filter((b) => b.count > 0)
        .map((b) => ({
          label: b.key === 'CLEAR' ? 'Verified'
            : b.key === 'SECONDARY_REVIEW' ? 'Re-capture'
              : b.key === 'HOLD_REFER' ? 'Manual Verification'
                : b.key.replace(/_/g, ' '),
          value: b.count,
          color: b.key === 'CLEAR'
            ? 'hsl(var(--status-clear))'
            : b.key === 'HOLD_REFER'
              ? 'hsl(var(--status-high))'
              : 'hsl(var(--status-review))',
        }))
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Case counts, workload, and system status.
        </p>
      </div>

      {/* Top KPI row */}
      <Card title="Case Overview">
        {immigration.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {immigration.status === 'forbidden' && <NoAccessNote what="immigration case counts" />}
        {immigration.status === 'error' && <p className="text-sm text-status-high">{immigration.message}</p>}
        {immigration.status === 'ok' && immigration.data && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="New Cases" value={immigration.data.new_cases} icon={FileText} delay={0} />
            <StatTile label="Pending Review" value={immigration.data.pending_review} accent="review" icon={Clock} delay={80} />
            <StatTile label="High Priority" value={immigration.data.high_priority} accent="high" icon={AlertTriangle} delay={160} />
            <StatTile label="Verified" value={immigration.data.cleared_cases} accent="clear" icon={CheckCircle2} delay={240} />
          </div>
        )}
      </Card>

      {/* Middle row: checkpoint bars + risk donut + daily trend */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Checkpoint Workload" className="lg:col-span-2">
          {supervisor.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
          {supervisor.status === 'forbidden' && <NoAccessNote what="the cross-checkpoint workload" />}
          {supervisor.status === 'error' && <p className="text-sm text-status-high">{supervisor.message}</p>}
          {supervisor.status === 'ok' && supervisor.data && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatTile label="Total Scans" value={supervisor.data.total_scans} icon={Radio} />
                <StatTile label="Pending" value={supervisor.data.pending_cases} icon={Clock} />
                <StatTile label="Review Required" value={supervisor.data.review_required} accent="review" icon={AlertTriangle} />
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

        {/* System health */}
        <Card title="System">
          {(admin.status === 'loading' || health.status === 'loading') && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {admin.status === 'forbidden' && <NoAccessNote what="system/admin data" />}
          {admin.status === 'ok' && admin.data && (
            <div className="space-y-3">
              <StatTile label="Registered Users" value={admin.data.registered_users} icon={UsersIcon} />
              <StatTile label="Devices" value={admin.data.registered_devices} icon={HardDrive} />
              <StatTile label="Sync Queue" value={admin.data.sync_queue_pending} icon={Server} />
            </div>
          )}
          {health.status === 'ok' && health.data && (
            <dl className="mt-4 grid grid-cols-1 gap-3 border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Database</dt>
                <dd className={`text-sm font-medium ${health.data.database_status === 'ok' ? 'text-status-clear' : 'text-status-high'}`}>
                  {health.data.database_status}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Pipeline</dt>
                <dd className="text-sm font-medium text-foreground">{health.data.analysis_pipeline_status}</dd>
              </div>
            </dl>
          )}
        </Card>
      </div>

      {/* Analytics row: risk donut + decision donut + daily trend */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Risk Distribution">
          {analytics.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
          {analytics.status === 'forbidden' && <NoAccessNote what="analytics" />}
          {analytics.status === 'ok' && analytics.data && riskSlices.length > 0 ? (
            <DonutChart slices={riskSlices} />
          ) : analytics.status === 'ok' ? (
            <p className="text-sm text-muted-foreground">No screening data yet.</p>
          ) : null}
        </Card>

        <Card title="Decision Outcomes">
          {analytics.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
          {analytics.status === 'ok' && analytics.data && decisionSlices.length > 0 ? (
            <DonutChart slices={decisionSlices} />
          ) : analytics.status === 'ok' ? (
            <p className="text-sm text-muted-foreground">No decisions recorded yet.</p>
          ) : null}
        </Card>

        <Card title="Daily Screenings (14 days)">
          {analytics.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
          {analytics.status === 'ok' && analytics.data && analytics.data.by_day.length > 0 ? (
            <DailyBars buckets={analytics.data.by_day} />
          ) : analytics.status === 'ok' ? (
            <p className="text-sm text-muted-foreground">No data for this period.</p>
          ) : null}
          {analytics.status === 'ok' && analytics.data && (
            <p className="mt-3 text-right text-xs text-muted-foreground">
              {analytics.data.total_screenings} total screenings
            </p>
          )}
        </Card>
      </div>

      {/* Recent cases */}
      <Card title="Recent Cases">
        {cases.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {cases.status === 'forbidden' && <NoAccessNote what="the case queue" />}
        {cases.status === 'error' && <p className="text-sm text-status-high">{cases.message}</p>}
        {cases.status === 'ok' && cases.data && <CaseTable cases={cases.data} />}
      </Card>
    </div>
  )
}
