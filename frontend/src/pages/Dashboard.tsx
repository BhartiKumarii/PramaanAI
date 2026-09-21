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

  // AI analysis outcomes — by_decision tracks the risk engine's decision
  // (CLEAR = no flags, MANUAL_REVIEW = flagged for human review), NOT officer decisions
  const aiOutcomeData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_decision
        .filter((b) => b.count > 0)
        .map((b) => ({
          name: b.key === 'CLEAR' ? 'No Flags Raised' : 'Flagged for Review',
          value: b.count,
          color: b.key === 'CLEAR' ? COLOR_CLEAR : COLOR_REVIEW,
        }))
    : []

  // Daily trend
  const dayData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_day.slice(-14).map((b) => ({ date: b.key.slice(5), count: b.count }))
    : []

  // Week-on-week trend (capped at ±99 to avoid extreme display)
  const last7  = dayData.slice(-7).reduce((s, b) => s + b.count, 0)
  const prev7  = dayData.slice(0, 7).reduce((s, b) => s + b.count, 0)
  const rawTrend = prev7 > 0 ? Math.round(((last7 - prev7) / prev7) * 100) : null
  const trendPct = rawTrend !== null ? Math.max(-99, Math.min(99, rawTrend)) : null
  const trendCapped = rawTrend !== null && Math.abs(rawTrend) > 99

  // Document type bar data — proper display names
  const DOC_DISPLAY: Record<string, string> = {
    passport: 'Passport',
    visa: 'Visa',
    national_id: 'National ID',
    driving_licence: 'Driving Licence',
    driving_license: 'Driving Licence',
    permit: 'Permit / ILP',
    aadhaar: 'Aadhaar',
    pan_card: 'PAN Card',
    voter_id: 'Voter ID',
  }
  const docTypeData = analytics.status === 'ok' && analytics.data
    ? analytics.data.by_document_type.map((b) => ({
        type: DOC_DISPLAY[b.key] ?? b.key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        count: b.count,
      }))
    : []

  // Flagged rate
  const totalAI = aiOutcomeData.reduce((s, d) => s + d.value, 0)
  const flaggedCount = aiOutcomeData.find((d) => d.name === 'Flagged for Review')?.value ?? 0
  const flaggedRate = totalAI > 0 ? Math.round((flaggedCount / totalAI) * 100) : null

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
                ['Database',   health.data.database_status],
                ['Analysis',   health.data.analysis_pipeline_status],
              ] as [string, string][]).map(([label, val]) => {
                const ok = val.toLowerCase().startsWith('ok')
                return (
                  <div key={label} className="flex items-center justify-between">
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
                    <dd className={`text-sm font-medium ${ok ? 'text-status-clear' : 'text-status-high'}`}>
                      {ok ? '✓ Online' : '✗ Issue'}
                    </dd>
                  </div>
                )
              })}
            </dl>
          )}
        </Card>
      </div>

      {/* Analytics charts row */}
      {analytics.status === 'ok' && analytics.data && (
        <>
          {/* Analytics KPI row */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Screenings (14 days)" value={analytics.data.total_screenings} icon={FileText} />
            <StatTile label="This Week" value={last7} icon={TrendingUp} />
            {flaggedRate !== null && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Flagged Rate</p>
                <p className={`mt-2 text-2xl font-semibold ${flaggedRate > 50 ? 'text-status-review' : 'text-status-clear'}`}>
                  {flaggedRate}%
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">of screenings flagged by AI</p>
              </div>
            )}
            {trendPct !== null && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">vs Prior Week</p>
                <p className={`mt-2 text-2xl font-semibold ${trendPct > 0 ? 'text-status-review' : 'text-status-clear'}`}>
                  {trendPct > 0 ? '+' : ''}{trendPct}{trendCapped ? '+' : ''}%
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {last7} this week · {prev7} last week
                </p>
              </div>
            )}
          </div>

          {/* Row: Daily trend + Risk pie */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card title="Screenings per Day — last 14 days" className="lg:col-span-2">
              {dayData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No data yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={210}>
                  <AreaChart data={dayData} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
                    <defs>
                      <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={COLOR_CHART1} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={COLOR_CHART1} stopOpacity={0}   />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="2 4" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="date"
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      tickLine={false} axisLine={false}
                      interval="preserveStartEnd" />
                    <YAxis allowDecimals={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      labelFormatter={(l) => `Date: ${l}`}
                      formatter={(v) => [v, 'Screenings']} />
                    <Area type="monotone" dataKey="count" name="Screenings"
                      stroke={COLOR_CHART1} fill="url(#grad)" strokeWidth={2.5} dot={false}
                      activeDot={{ r: 4, fill: COLOR_CHART1, strokeWidth: 0 }} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Risk Level Distribution">
              {riskData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={170}>
                    <PieChart>
                      <Pie data={riskData} dataKey="value" nameKey="name"
                        cx="50%" cy="50%"
                        innerRadius={48} outerRadius={72}
                        paddingAngle={3} strokeWidth={0} startAngle={90} endAngle={-270}>
                        {riskData.map((d) => <Cell key={d.name} fill={d.color} />)}
                      </Pie>
                      <Tooltip contentStyle={TOOLTIP_STYLE}
                        formatter={(v, n) => [`${v} screenings`, String(n)]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <ul className="mt-1 space-y-1.5 text-sm">
                    {riskData.map((d) => {
                      const total = riskData.reduce((s, x) => s + x.value, 0)
                      const pct = total > 0 ? Math.round((d.value / total) * 100) : 0
                      return (
                        <li key={d.name} className="flex items-center gap-2">
                          <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: d.color }} />
                          <span className="flex-1 text-muted-foreground">{d.name}</span>
                          <span className="font-semibold text-foreground">{d.value}</span>
                          <span className="w-8 text-right text-xs text-muted-foreground">{pct}%</span>
                        </li>
                      )
                    })}
                  </ul>
                </>
              )}
            </Card>
          </div>

          {/* Row: AI outcomes + Document types */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="AI Analysis Outcomes">
              <p className="mb-3 text-xs text-muted-foreground">
                Automatic risk assessment result for each screening — not the final officer decision.
              </p>
              {aiOutcomeData.length === 0 ? (
                <p className="py-4 text-sm text-muted-foreground">No analysis data yet.</p>
              ) : (
                <div className="space-y-3">
                  {aiOutcomeData.map((d) => {
                    const total = aiOutcomeData.reduce((s, x) => s + x.value, 0)
                    const pct = total > 0 ? (d.value / total) * 100 : 0
                    return (
                      <div key={d.name}>
                        <div className="mb-1 flex justify-between text-sm">
                          <span className="font-medium" style={{ color: d.color }}>{d.name}</span>
                          <span className="text-foreground font-semibold">{d.value} <span className="text-muted-foreground font-normal text-xs">({Math.round(pct)}%)</span></span>
                        </div>
                        <div className="h-3 overflow-hidden rounded-full bg-secondary">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: d.color }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>

            <Card title="Documents Screened by Type">
              {docTypeData.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={docTypeData} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
                    <CartesianGrid strokeDasharray="2 4" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="type"
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      tickLine={false} axisLine={false} />
                    <YAxis allowDecimals={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE}
                      formatter={(v) => [v, 'Screenings']} />
                    <Bar dataKey="count" fill={COLOR_CHART1}
                      radius={[5, 5, 0, 0]} name="Screenings"
                      maxBarSize={52} />
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
