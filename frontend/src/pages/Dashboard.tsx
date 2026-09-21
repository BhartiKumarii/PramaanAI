import { useEffect, useState } from 'react'
import {
  FileText, Clock, AlertTriangle, CheckCircle2,
  Radio, Users as UsersIcon, Server, HardDrive, TrendingUp,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell,
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

// ── Color constants (solid hex — not CSS variables, safe in SVG/canvas) ──────
const COLOR_CLEAR   = '#22c55e'
const COLOR_REVIEW  = '#f59e0b'
const COLOR_HIGH    = '#ef4444'
const COLOR_CHART1  = '#6366f1'

const TOOLTIP_STYLE = {
  background: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))',
  borderRadius: 8,
  fontSize: 12,
}

// ── Checkpoint stacked bar chart ──────────────────────────────────────────────

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
          { key: 'pending',  value: row.pending,          label: 'Pending',   color: COLOR_CHART1   },
          { key: 'review',   value: row.review_required,  label: 'Review',    color: COLOR_REVIEW   },
          { key: 'cleared',  value: row.cleared,          label: 'Verified',  color: COLOR_CLEAR    },
        ]
        return (
          <div key={row.checkpoint_code}>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="font-medium text-foreground">{row.checkpoint_code}</span>
              <span className="flex gap-3 text-xs text-muted-foreground">
                {segments.map((s) => (
                  <span key={s.key} className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
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
                  className="h-full transition-all duration-700 ease-out"
                  style={{
                    width: mounted ? `${(seg.value / total) * 100}%` : '0%',
                    transitionDelay: `${index * 80}ms`,
                    background: seg.color,
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

// ── Main component ────────────────────────────────────────────────────────────

export function Dashboard() {
  const immigration = useSection<ImmigrationDashboardData>(getImmigrationDashboard)
  const supervisor  = useSection<SupervisorDashboardData>(getSupervisorDashboard)
  const admin       = useSection<AdminDashboardData>(getAdminDashboard)
  const health      = useSection<SystemHealth>(getSystemHealth)
  const analytics   = useSection<AnalyticsDashboard>(() => getAnalyticsDashboard(14))
  const cases       = useSection<CaseListItem[]>(() => listCases({ limit: 10 }))

  // Risk distribution data for pie chart
  const riskData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_risk_level.map((b) => ({
        name: b.key === 'HIGH_RISK' ? 'High Risk' : b.key === 'MEDIUM_RISK' ? 'Medium Risk' : 'Low Risk',
        value: b.count,
        color: b.key === 'HIGH_RISK' ? COLOR_HIGH : b.key === 'MEDIUM_RISK' ? COLOR_REVIEW : COLOR_CLEAR,
      }))
    : []

  // Decision data for pie chart
  const decisionData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_decision
        .filter((b) => b.count > 0)
        .map((b) => ({
          name: b.key === 'CLEAR' ? 'Verified' : b.key === 'SECONDARY_REVIEW' ? 'Re-capture' : b.key === 'HOLD_REFER' ? 'Manual Review' : b.key,
          value: b.count,
          color: b.key === 'CLEAR' ? COLOR_CLEAR : b.key === 'HOLD_REFER' ? COLOR_HIGH : COLOR_REVIEW,
        }))
    : []

  // Daily trend
  const dayData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_day.slice(-14).map((b) => ({ date: b.key.slice(5), count: b.count }))
    : []

  // Week-on-week trend
  const last7  = dayData.slice(-7).reduce((s, b) => s + b.count, 0)
  const prev7  = dayData.slice(0, 7).reduce((s, b) => s + b.count, 0)
  const trendPct = prev7 > 0 ? Math.round(((last7 - prev7) / prev7) * 100) : null

  // Document type bar data
  const docTypeData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_document_type.map((b) => ({ type: b.key.replace('_', ' '), count: b.count }))
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Live case counts, workload, and system status.</p>
      </div>

      {/* KPI row */}
      <Card title="Case Overview">
        {immigration.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {immigration.status === 'forbidden' && <NoAccessNote what="immigration case counts" />}
        {immigration.status === 'error' && <p className="text-sm text-status-high">{immigration.message}</p>}
        {immigration.status === 'ok' && immigration.data && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="New Cases"       value={immigration.data.new_cases}     icon={FileText}      delay={0} />
            <StatTile label="Pending Review"  value={immigration.data.pending_review} accent="review" icon={Clock}       delay={80} />
            <StatTile label="High Priority"   value={immigration.data.high_priority} accent="high"   icon={AlertTriangle} delay={160} />
            <StatTile label="Verified"        value={immigration.data.cleared_cases} accent="clear"  icon={CheckCircle2}  delay={240} />
          </div>
        )}
      </Card>

      {/* Checkpoint workload + system */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Checkpoint Workload" className="lg:col-span-2">
          {supervisor.status === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
          {supervisor.status === 'forbidden' && <NoAccessNote what="checkpoint workload" />}
          {supervisor.status === 'ok' && supervisor.data && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatTile label="Total Scans"    value={supervisor.data.total_scans}      icon={Radio} />
                <StatTile label="Pending"        value={supervisor.data.pending_cases}     icon={Clock} />
                <StatTile label="Needs Review"   value={supervisor.data.review_required}  accent="review" icon={AlertTriangle} />
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
          {admin.status === 'forbidden' && <NoAccessNote what="system data" />}
          {admin.status === 'ok' && admin.data && (
            <div className="space-y-3">
              <StatTile label="Users"      value={admin.data.registered_users}   icon={UsersIcon} />
              <StatTile label="Devices"    value={admin.data.registered_devices} icon={HardDrive} />
              <StatTile label="Sync Queue" value={admin.data.sync_queue_pending} icon={Server} />
            </div>
          )}
          {health.status === 'ok' && health.data && (
            <dl className="mt-4 space-y-2 border-t border-border pt-4">
              {([
                ['Database',  health.data.database_status],
                ['Pipeline',  health.data.analysis_pipeline_status],
              ] as [string, string][]).map(([label, val]) => (
                <div key={label} className="flex items-center justify-between">
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
                  <dd className={`text-sm font-medium ${val === 'ok' ? 'text-status-clear' : 'text-foreground'}`}>
                    {val === 'ok' ? '✓ OK' : val.slice(0, 20)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </Card>
      </div>

      {/* Analytics charts row */}
      {analytics.status === 'ok' && analytics.data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Total Screenings (14d)" value={analytics.data.total_screenings} icon={FileText} />
            <StatTile label="Last 7 days"             value={last7}   icon={TrendingUp}
              accent={trendPct !== null && trendPct > 20 ? 'review' : undefined} />
            <StatTile label="Decisions Recorded"
              value={analytics.data.by_decision.reduce((s, b) => s + b.count, 0)}
              icon={CheckCircle2} accent="clear" />
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Trend vs prev week</p>
              <p className={`mt-2 text-2xl font-semibold ${trendPct === null ? 'text-muted-foreground' : trendPct >= 0 ? 'text-status-review' : 'text-status-clear'}`}>
                {trendPct === null ? '—' : `${trendPct >= 0 ? '+' : ''}${trendPct}%`}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">screening volume</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Daily trend */}
            <Card title="Daily Screening Volume (14 days)" className="lg:col-span-2">
              {dayData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No data yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={dayData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                    <defs>
                      <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={COLOR_CHART1} stopOpacity={0.35} />
                        <stop offset="95%" stopColor={COLOR_CHART1} stopOpacity={0}    />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      interval="preserveStartEnd" />
                    <YAxis allowDecimals={false} tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={(l) => `Date: ${l}`} />
                    <Area type="monotone" dataKey="count" name="Screenings"
                      stroke={COLOR_CHART1} fill="url(#grad)" strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>

            {/* Risk distribution pie */}
            <Card title="Risk Distribution">
              {riskData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie data={riskData} dataKey="value" nameKey="name"
                        innerRadius={42} outerRadius={68} paddingAngle={2} strokeWidth={0}>
                        {riskData.map((d) => <Cell key={d.name} fill={d.color} />)}
                      </Pie>
                      <Tooltip contentStyle={TOOLTIP_STYLE}
                        formatter={(v, n) => [`${v} cases`, String(n)]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <ul className="mt-2 space-y-1 text-xs">
                    {riskData.map((d) => (
                      <li key={d.name} className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: d.color }} />
                        <span className="flex-1 text-muted-foreground">{d.name}</span>
                        <span className="font-semibold text-foreground">{d.value}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Decision outcomes */}
            <Card title="Verification Decisions">
              {decisionData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No decisions recorded yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={decisionData} layout="vertical"
                    margin={{ top: 4, right: 40, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                    <XAxis type="number" allowDecimals={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" width={100}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} />
                    <Tooltip contentStyle={TOOLTIP_STYLE}
                      formatter={(v) => [`${v} cases`, 'Count']} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]} name="Cases">
                      {decisionData.map((d) => <Cell key={d.name} fill={d.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            {/* Document types */}
            <Card title="Document Types Screened">
              {docTypeData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={docTypeData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="type" tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} />
                    <YAxis allowDecimals={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="count" fill={COLOR_CHART1} radius={[4, 4, 0, 0]} name="Screenings" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>
        </>
      )}

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
