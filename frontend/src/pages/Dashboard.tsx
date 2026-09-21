import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, CheckCircle2, Clock, FileText,
  HardDrive, Radio, Server, Shield, Users as UsersIcon,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, Cell,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
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

// ── Data fetching ────────────────────────────────────────────────────────────

type SectionState<T> = {
  status: 'loading' | 'ok' | 'forbidden' | 'error'
  data: T | null
  message?: string
}

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

// ── Tooltip ──────────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number; name?: string }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-foreground">{label}</p>
      <p className="mt-0.5 text-muted-foreground">{payload[0].value} {payload[0].name ?? 'screenings'}</p>
    </div>
  )
}

// ── Checkpoint progress bars ──────────────────────────────────────────────────

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
    <div className="space-y-5">
      {rows.map((row, i) => {
        const total = row.pending + row.review_required + row.cleared || 1
        const items = [
          { key: 'pending', label: 'Pending',  value: row.pending,         color: 'var(--color-chart-1)' },
          { key: 'review',  label: 'Review',   value: row.review_required, color: 'var(--color-status-review)' },
          { key: 'cleared', label: 'Verified', value: row.cleared,         color: 'var(--color-status-clear)' },
        ]
        return (
          <div key={row.checkpoint_code}>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-foreground">{row.checkpoint_code}</span>
              <span className="text-xs text-muted-foreground">{total} total</span>
            </div>
            <div className="flex h-2 overflow-hidden rounded-full bg-secondary">
              {items.map((seg) => (
                <div
                  key={seg.key}
                  title={`${seg.label}: ${seg.value}`}
                  className="h-full transition-all duration-700 ease-out"
                  style={{
                    width: mounted ? `${(seg.value / total) * 100}%` : '0%',
                    background: seg.color,
                    transitionDelay: `${i * 60}ms`,
                  }}
                />
              ))}
            </div>
            <div className="mt-1.5 flex gap-4">
              {items.map((seg) => (
                <span key={seg.key} className="flex items-center gap-1 text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full" style={{ background: seg.color }} />
                  {seg.value} {seg.label}
                </span>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function Dashboard() {
  const navigate = useNavigate()
  const immigration = useSection<ImmigrationDashboardData>(getImmigrationDashboard)
  const supervisor  = useSection<SupervisorDashboardData>(getSupervisorDashboard)
  const admin       = useSection<AdminDashboardData>(getAdminDashboard)
  const health      = useSection<SystemHealth>(getSystemHealth)
  const analytics   = useSection<AnalyticsDashboard>(() => getAnalyticsDashboard(7))
  const cases       = useSection<CaseListItem[]>(() => listCases({ limit: 8 }))

  const d = analytics.data

  // 7-day trend for the small sparkline
  const trendData = d?.by_day.slice(-7) ?? []

  // Risk slices for the donut
  const riskSlices = d?.by_risk_level.map((b) => ({
    name: b.key === 'HIGH_RISK' ? 'High Risk' : b.key === 'MEDIUM_RISK' ? 'Medium Risk' : 'Low Risk',
    value: b.count,
    color:
      b.key === 'HIGH_RISK'   ? 'var(--color-status-high)' :
      b.key === 'MEDIUM_RISK' ? 'var(--color-status-review)' :
      'var(--color-status-clear)',
  })) ?? []

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Overview</h1>
        <p className="text-sm text-muted-foreground">
          Live operational status — cases needing action, checkpoint activity, and system health.
        </p>
      </div>

      {/* ── Action Required banner ── */}
      {immigration.status === 'ok' && immigration.data &&
        (immigration.data.pending_review > 0 || immigration.data.high_priority > 0) && (
        <button
          onClick={() => navigate('/console/requests')}
          className="flex w-full items-center justify-between rounded-xl border border-status-review/40 bg-status-review-bg px-5 py-4 text-left hover:border-status-review/60 transition-colors"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-status-review shrink-0" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                {immigration.data.pending_review} case{immigration.data.pending_review !== 1 ? 's' : ''} waiting for review
              </p>
              <p className="text-xs text-muted-foreground">
                {immigration.data.high_priority > 0
                  ? `${immigration.data.high_priority} high priority · `
                  : ''}
                Tap to open the review queue
              </p>
            </div>
          </div>
          <span className="text-xs font-medium text-status-review">Open queue →</span>
        </button>
      )}

      {/* ── 4 KPI tiles: case counts (live) ── */}
      {immigration.status === 'ok' && immigration.data ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile label="New Cases Today"   value={immigration.data.new_cases}      icon={FileText}      delay={0}   />
          <StatTile label="Pending Review"    value={immigration.data.pending_review} icon={Clock}        accent="review" delay={60}  />
          <StatTile label="High Priority"     value={immigration.data.high_priority}  icon={AlertTriangle} accent="high"   delay={120} />
          <StatTile label="Verified Today"    value={immigration.data.cleared_cases}  icon={CheckCircle2}  accent="clear"  delay={180} />
        </div>
      ) : immigration.status === 'loading' ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0,1,2,3].map(i => (
            <div key={i} className="h-24 animate-pulse rounded-xl border border-border bg-secondary" />
          ))}
        </div>
      ) : null}

      {/* ── Middle row: Checkpoint workload + 7-day trend ── */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Checkpoint breakdown */}
        <Card title="Checkpoint Workload" className="lg:col-span-2">
          {supervisor.status === 'loading' && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {supervisor.status === 'ok' && supervisor.data && (
            <div className="space-y-5">
              {/* Summary row */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatTile label="Total Scans"     value={supervisor.data.total_scans}      icon={Radio}      />
                <StatTile label="Pending"         value={supervisor.data.pending_cases}     icon={Clock}      />
                <StatTile label="Needs Review"    value={supervisor.data.review_required}   icon={AlertTriangle} accent="review" />
                <StatTile label="Active Officers" value={supervisor.data.active_officers}   icon={UsersIcon}  />
              </div>
              {supervisor.data.checkpoint_breakdown.length > 0 && (
                <div className="border-t border-border pt-5">
                  <CheckpointBars rows={supervisor.data.checkpoint_breakdown} />
                </div>
              )}
            </div>
          )}
        </Card>

        {/* 7-day trend sparkline + system health */}
        <div className="space-y-5">
          <Card title="Screenings — Last 7 Days">
            {analytics.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
            {trendData.length > 0 && (
              <ResponsiveContainer width="100%" height={130}>
                <AreaChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
                  <defs>
                    <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"  stopColor="var(--color-accent)" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis
                    dataKey="key"
                    tick={{ fill: 'var(--color-muted-foreground)', fontSize: 10 }}
                    tickLine={false} axisLine={false}
                    tickFormatter={(v: string) => v.slice(5)}
                    interval="preserveStartEnd"
                  />
                  <YAxis allowDecimals={false} tick={false} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone" dataKey="count" name="screenings"
                    stroke="var(--color-accent)" fill="url(#trendGrad)"
                    strokeWidth={2}
                    dot={{ r: 3, fill: 'var(--color-accent)', strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="System Status">
            {admin.status === 'ok' && admin.data && (
              <div className="space-y-2 pb-3 border-b border-border mb-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground flex items-center gap-2">
                    <UsersIcon className="h-3.5 w-3.5" /> Users
                  </span>
                  <span className="font-medium text-foreground">{admin.data.registered_users}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground flex items-center gap-2">
                    <HardDrive className="h-3.5 w-3.5" /> Devices
                  </span>
                  <span className="font-medium text-foreground">{admin.data.registered_devices}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground flex items-center gap-2">
                    <Server className="h-3.5 w-3.5" /> Sync Queue
                  </span>
                  <span className="font-medium text-foreground">{admin.data.sync_queue_pending}</span>
                </div>
              </div>
            )}
            {health.status === 'ok' && health.data && (
              <div className="space-y-2">
                {([
                  ['Database',    health.data.database_status],
                  ['Analysis',    health.data.analysis_pipeline_status],
                ] as [string, string][]).map(([label, val]) => {
                  const ok = val.toLowerCase().startsWith('ok')
                  return (
                    <div key={label} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{label}</span>
                      <span className={`flex items-center gap-1 text-xs font-semibold ${ok ? 'text-status-clear' : 'text-status-high'}`}>
                        {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                        {ok ? 'Online' : 'Issue'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* ── Risk distribution donut ── */}
      {riskSlices.length > 0 && d && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="Risk Level Distribution — Last 7 Days">
            <div className="relative">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={riskSlices}
                    dataKey="value" nameKey="name"
                    innerRadius={60} outerRadius={90}
                    paddingAngle={3} strokeWidth={0}
                    startAngle={90} endAngle={-270}
                  >
                    {riskSlices.map((s) => <Cell key={s.name} fill={s.color} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'var(--color-card)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(v: unknown, n: unknown) => [String(v) + ' screenings', String(n)]}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Centre label */}
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ marginBottom: 40 }}>
                <div className="text-center">
                  <p className="text-2xl font-bold text-foreground">{d.total_screenings}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Screenings</p>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap justify-center gap-5 text-xs text-muted-foreground">
              {riskSlices.map((s) => {
                const pct = d.total_screenings > 0 ? Math.round((s.value / d.total_screenings) * 100) : 0
                return (
                  <span key={s.name} className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
                    {s.name} — <span className="font-semibold text-foreground">{s.value}</span>
                    <span className="text-muted-foreground/70">({pct}%)</span>
                  </span>
                )
              })}
            </div>
          </Card>

          {/* Operational mini-metrics */}
          <div className="grid grid-cols-1 gap-4 content-start">
            {[
              {
                icon: Shield,
                label: 'Screening Velocity',
                value: d.total_screenings > 0 ? (d.total_screenings / 7).toFixed(1) : '0',
                sub: 'screenings per day (7-day avg)',
              },
              {
                icon: AlertTriangle,
                label: 'High Risk Rate',
                value: d.total_screenings > 0
                  ? `${Math.round(((d.by_risk_level.find(b => b.key === 'HIGH_RISK')?.count ?? 0) / d.total_screenings) * 100)}%`
                  : '0%',
                sub: 'of screenings flagged high risk',
              },
              {
                icon: FileText,
                label: 'Document Types Seen',
                value: d.by_document_type.filter(b => b.count > 0).length,
                sub: 'different document types scanned',
              },
            ].map(({ icon: Icon, label, value, sub }) => (
              <Card key={label}>
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
                    <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
                    <p className="text-xs text-muted-foreground">{sub}</p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* ── Recent cases ── */}
      <Card title="Recent Cases">
        {cases.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {cases.status === 'ok' && cases.data && cases.data.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No cases yet.</p>
        )}
        {cases.status === 'ok' && cases.data && cases.data.length > 0 && (
          <CaseTable cases={cases.data} />
        )}
      </Card>
    </div>
  )
}
