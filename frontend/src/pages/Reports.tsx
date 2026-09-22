import { useState, useMemo } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAnalyticsDashboard } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card, StatTile } from '../components/StatTile'
import { BarChart3, TrendingUp, Shield, Activity, Calendar, Percent } from 'lucide-react'

const PERIOD_OPTIONS = [
  { label: '7 Days', value: 7 },
  { label: '14 Days', value: 14 },
  { label: '30 Days', value: 30 },
  { label: '90 Days', value: 90 },
]

const RISK_COLOR: Record<string, string> = {
  LOW_RISK: 'var(--color-status-clear)',
  MEDIUM_RISK: 'var(--color-status-review)',
  HIGH_RISK: 'var(--color-status-high)',
}

const RISK_LABEL: Record<string, string> = {
  LOW_RISK: 'Low Risk',
  MEDIUM_RISK: 'Medium Risk',
  HIGH_RISK: 'High Risk',
}

const DECISION_COLOR: Record<string, string> = {
  CLEAR: 'var(--color-status-clear)',
  MANUAL_REVIEW: 'var(--color-status-review)',
}

const DECISION_LABEL: Record<string, string> = {
  CLEAR: 'Cleared',
  MANUAL_REVIEW: 'Manual Review',
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-foreground">{label}</p>
      <p className="mt-0.5 text-muted-foreground">{payload[0].value} screenings</p>
    </div>
  )
}

export function Reports() {
  const [days, setDays] = useState(14)
  const analytics = useAsync(() => getAnalyticsDashboard(days), [days])

  const derived = useMemo(() => {
    if (!analytics.data) return null
    const d = analytics.data

    const clearCount = d.by_decision.find((b) => b.key === 'CLEAR')?.count ?? 0
    const reviewCount = d.by_decision.find((b) => b.key === 'MANUAL_REVIEW')?.count ?? 0
    const total = d.total_screenings || 1

    const clearRate = Math.round((clearCount / total) * 100)
    const reviewRate = Math.round((reviewCount / total) * 100)
    const avgPerDay = +(d.total_screenings / days).toFixed(1)

    const peakEntry = d.by_day.reduce(
      (best, cur) => (cur.count > best.count ? cur : best),
      { key: '—', count: 0 },
    )

    const riskWeighted = d.by_risk_level.reduce((sum, b) => {
      const weight = b.key === 'LOW_RISK' ? 20 : b.key === 'MEDIUM_RISK' ? 55 : 85
      return sum + weight * b.count
    }, 0)
    const avgRiskScore = d.total_screenings ? Math.round(riskWeighted / d.total_screenings) : 0

    const checkpointCount = new Set(d.by_day.map((b) => b.key)).size > 0 ? d.by_document_type.length : 0

    return { clearCount, reviewCount, clearRate, reviewRate, avgPerDay, peakEntry, avgRiskScore, checkpointCount }
  }, [analytics.data, days])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Analytics &amp; Intelligence</h1>
          <p className="text-sm text-muted-foreground">
            Screening volume, document verification insights, risk distribution, and operational metrics — all real-time.
          </p>
        </div>
        <div className="flex gap-1.5">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                days === opt.value
                  ? 'bg-accent text-accent-foreground'
                  : 'border border-border text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {analytics.loading && <p className="text-sm text-muted-foreground">Loading analytics…</p>}
      {analytics.error && <p className="text-sm text-status-high">{analytics.error}</p>}

      {analytics.data && derived && (
        <>
          {/* Row 1: Key metrics */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile
              label={`Total Screenings (${days}d)`}
              value={analytics.data.total_screenings}
              icon={BarChart3}
              delay={0}
            />
            <StatTile
              label="Clear Rate"
              value={`${derived.clearRate}%`}
              accent="clear"
              icon={Shield}
              delay={80}
            />
            <StatTile
              label="Avg. Risk Score"
              value={derived.avgRiskScore}
              accent={derived.avgRiskScore > 60 ? 'high' : derived.avgRiskScore > 35 ? 'review' : 'clear'}
              icon={Activity}
              delay={160}
            />
            <StatTile
              label="Document Types Seen"
              value={analytics.data.by_document_type.length}
              icon={Percent}
              delay={240}
            />
          </div>

          {/* Row 2: Volume trend + Risk distribution */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card title="Screening Volume Trend">
              {analytics.data.by_day.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No screenings in this window.</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={analytics.data.by_day}>
                    <defs>
                      <linearGradient id="volumeGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="key" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="count"
                      stroke="var(--color-accent)"
                      strokeWidth={2}
                      fill="url(#volumeGrad)"
                      dot={{ r: 3, fill: 'var(--color-accent)' }}
                      activeDot={{ r: 5 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Risk Distribution">
              {analytics.data.by_risk_level.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <>
                  <div className="relative">
                    <ResponsiveContainer width="100%" height={220}>
                      <PieChart>
                        <Pie
                          data={analytics.data.by_risk_level}
                          dataKey="count"
                          nameKey="key"
                          innerRadius={60}
                          outerRadius={90}
                          paddingAngle={3}
                          strokeWidth={0}
                        >
                          {analytics.data.by_risk_level.map((b) => (
                            <Cell key={b.key} fill={RISK_COLOR[b.key] ?? 'var(--color-muted-foreground)'} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            background: 'var(--color-card)',
                            border: '1px solid var(--color-border)',
                            fontSize: 12,
                            borderRadius: 8,
                          }}
                          formatter={(value: unknown, name: unknown) => [String(value), RISK_LABEL[String(name)] ?? String(name)]}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ marginBottom: 40 }}>
                      <div className="text-center">
                        <p className="text-2xl font-bold text-foreground">{analytics.data.total_screenings}</p>
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Total</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap justify-center gap-4 text-xs text-muted-foreground">
                    {analytics.data.by_risk_level.map((b) => {
                      const pct = analytics.data!.total_screenings
                        ? Math.round((b.count / analytics.data!.total_screenings) * 100)
                        : 0
                      return (
                        <span key={b.key} className="flex items-center gap-1.5">
                          <span
                            className="h-2.5 w-2.5 rounded-full"
                            style={{ background: RISK_COLOR[b.key] ?? 'var(--color-muted-foreground)' }}
                          />
                          {RISK_LABEL[b.key] ?? b.key} — {b.count} ({pct}%)
                        </span>
                      )
                    })}
                  </div>
                </>
              )}
            </Card>
          </div>

          {/* Row 3: Document types + Decision outcomes */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card title="Document Types Analyzed">
              {analytics.data.by_document_type.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={analytics.data.by_document_type}
                    layout="vertical"
                    margin={{ left: 10 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                    <YAxis
                      type="category"
                      dataKey="key"
                      tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }}
                      width={100}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--color-card)',
                        border: '1px solid var(--color-border)',
                        fontSize: 12,
                        borderRadius: 8,
                      }}
                    />
                    <Bar dataKey="count" fill="var(--color-chart-1)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Decision Outcomes">
              {analytics.data.by_decision.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <>
                  <div className="mb-4 space-y-3">
                    {analytics.data.by_decision.map((b) => {
                      const pct = analytics.data!.total_screenings
                        ? Math.round((b.count / analytics.data!.total_screenings) * 100)
                        : 0
                      return (
                        <div key={b.key}>
                          <div className="mb-1.5 flex items-baseline justify-between text-sm">
                            <span className="font-medium text-foreground">{DECISION_LABEL[b.key] ?? b.key}</span>
                            <span className="text-xs text-muted-foreground">
                              {b.count} ({pct}%)
                            </span>
                          </div>
                          <div className="h-3 overflow-hidden rounded-full bg-secondary">
                            <div
                              className="h-full rounded-full transition-all duration-700"
                              style={{
                                width: `${pct}%`,
                                background: DECISION_COLOR[b.key] ?? 'var(--color-chart-2)',
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart
                      data={analytics.data.by_decision.map((b) => ({
                        ...b,
                        label: DECISION_LABEL[b.key] ?? b.key,
                      }))}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="label" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--color-card)',
                          border: '1px solid var(--color-border)',
                          fontSize: 12,
                          borderRadius: 8,
                        }}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {analytics.data.by_decision.map((b) => (
                          <Cell key={b.key} fill={DECISION_COLOR[b.key] ?? 'var(--color-chart-2)'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </>
              )}
            </Card>
          </div>

          {/* Row 4: Operational metrics */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                  <TrendingUp className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Screening Velocity
                  </p>
                  <p className="mt-1 text-2xl font-bold text-foreground">{derived.avgPerDay}</p>
                  <p className="text-xs text-muted-foreground">screenings / day avg</p>
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                  <Calendar className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Peak Activity</p>
                  <p className="mt-1 text-2xl font-bold text-foreground">{derived.peakEntry.key}</p>
                  <p className="text-xs text-muted-foreground">
                    {derived.peakEntry.count} screenings on busiest day
                  </p>
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                  <Shield className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Review Ratio</p>
                  <p className="mt-1 text-2xl font-bold text-foreground">{derived.reviewRate}%</p>
                  <p className="text-xs text-muted-foreground">
                    {derived.reviewCount} of {analytics.data.total_screenings} sent to manual review
                  </p>
                </div>
              </div>
            </Card>
          </div>

          {/* Row 5: Daily breakdown table */}
          {analytics.data.by_day.length > 0 && (
            <Card title="Daily Breakdown">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2.5 pr-4">Date</th>
                      <th className="py-2.5 pr-4 text-right">Screenings</th>
                      <th className="py-2.5 pr-4 text-right">Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.data.by_day.map((row, i) => {
                      const prev = i > 0 ? analytics.data!.by_day[i - 1].count : row.count
                      const delta = row.count - prev
                      return (
                        <tr key={row.key} className="border-b border-border last:border-0">
                          <td className="py-2.5 pr-4 font-medium text-foreground">{row.key}</td>
                          <td className="py-2.5 pr-4 text-right text-muted-foreground">{row.count}</td>
                          <td className="py-2.5 pr-4 text-right">
                            {i === 0 ? (
                              <span className="text-xs text-muted-foreground">—</span>
                            ) : delta > 0 ? (
                              <span className="text-xs text-status-clear">+{delta}</span>
                            ) : delta < 0 ? (
                              <span className="text-xs text-status-high">{delta}</span>
                            ) : (
                              <span className="text-xs text-muted-foreground">0</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
