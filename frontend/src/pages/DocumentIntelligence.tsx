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
import { FileText, TrendingUp } from 'lucide-react'

const LEVEL_COLOR: Record<string, string> = {
  LOW_RISK: 'var(--color-status-clear)',
  MEDIUM_RISK: 'var(--color-status-review)',
  HIGH_RISK: 'var(--color-status-high)',
}

const DECISION_COLOR: Record<string, string> = {
  CLEAR: 'var(--color-status-clear)',
  SECONDARY_REVIEW: 'var(--color-status-review)',
  HOLD_REFER: 'var(--color-status-high)',
}

const DECISION_LABEL: Record<string, string> = {
  CLEAR: 'Verified',
  SECONDARY_REVIEW: 'Re-capture Required',
  HOLD_REFER: 'Manual Verification',
}

const TOOLTIP_STYLE = {
  background: 'var(--color-card)',
  border: '1px solid var(--color-border)',
  fontSize: 12,
  borderRadius: 6,
}

export function DocumentIntelligence() {
  const analytics = useAsync(() => getAnalyticsDashboard(30), [])

  if (analytics.loading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (analytics.error) return <p className="text-sm text-status-high">{analytics.error}</p>
  if (!analytics.data) return null

  const d = analytics.data

  // Compute trend: screenings in last 7 days vs previous 7 days
  const days = d.by_day.slice(-14)
  const last7 = days.slice(-7).reduce((s, b) => s + b.count, 0)
  const prev7 = days.slice(0, 7).reduce((s, b) => s + b.count, 0)
  const trendPct = prev7 > 0 ? Math.round(((last7 - prev7) / prev7) * 100) : null

  // Verification rate
  const totalDecided = d.by_decision.reduce((s, b) => s + b.count, 0)
  const verified = d.by_decision.find((b) => b.key === 'CLEAR')?.count ?? 0
  const verifyRate = totalDecided > 0 ? Math.round((verified / totalDecided) * 100) : null

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Document Intelligence</h1>
        <p className="text-sm text-muted-foreground">
          Real aggregates from every screening scored in the last 30 days.
          All data comes directly from the verification pipeline — nothing estimated.
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Total Screenings (30d)" value={d.total_screenings} icon={FileText} />
        <StatTile
          label="Last 7 days"
          value={last7}
          icon={TrendingUp}
          accent={trendPct !== null && trendPct > 0 ? 'review' : undefined}
        />
        <StatTile
          label="Decisions recorded"
          value={totalDecided}
          icon={FileText}
          accent="clear"
        />
        {verifyRate !== null && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Verification rate</p>
            <p className="mt-2 text-2xl font-semibold text-status-clear">{verifyRate}%</p>
            <p className="mt-0.5 text-xs text-muted-foreground">of decided cases verified</p>
          </div>
        )}
      </div>

      {/* Row 1: daily trend + document types */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Daily screening volume (30 days)">
          {d.by_day.length === 0 ? (
            <p className="py-6 text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={d.by_day} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis
                    dataKey="key"
                    tick={{ fill: 'var(--color-muted-foreground)', fontSize: 10 }}
                    tickFormatter={(v: string) => v.slice(5)}
                    interval="preserveStartEnd"
                  />
                  <YAxis allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 10 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={(l) => `Date: ${l}`} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="var(--color-accent)"
                    fill="url(#areaGrad)"
                    strokeWidth={2}
                    dot={false}
                    name="Screenings"
                  />
                </AreaChart>
              </ResponsiveContainer>
              {trendPct !== null && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Last 7 days vs previous 7 days:{' '}
                  <span className={trendPct >= 0 ? 'text-status-review font-medium' : 'text-status-clear font-medium'}>
                    {trendPct >= 0 ? '+' : ''}{trendPct}%
                  </span>
                </p>
              )}
            </>
          )}
        </Card>

        <Card title="Document types screened">
          {d.by_document_type.length === 0 ? (
            <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={d.by_document_type} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="key" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} name="Screenings" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Row 2: risk distribution + decision outcomes */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Risk level distribution">
          {d.by_risk_level.length === 0 ? (
            <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={d.by_risk_level}
                    dataKey="count"
                    nameKey="key"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {d.by_risk_level.map((b) => (
                      <Cell key={b.key} fill={LEVEL_COLOR[b.key] ?? 'var(--color-muted-foreground)'} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(v, name) => [v, String(name).replace(/_/g, ' ')]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-1 flex flex-wrap justify-center gap-4 text-xs text-muted-foreground">
                {d.by_risk_level.map((b) => {
                  const pct = d.total_screenings > 0 ? Math.round((b.count / d.total_screenings) * 100) : 0
                  return (
                    <span key={b.key} className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full" style={{ background: LEVEL_COLOR[b.key] ?? 'var(--color-muted-foreground)' }} />
                      {b.key.replace(/_/g, ' ')} — {b.count} ({pct}%)
                    </span>
                  )
                })}
              </div>
            </>
          )}
        </Card>

        <Card title="Verification decision outcomes">
          {d.by_decision.filter((b) => b.count > 0).length === 0 ? (
            <p className="py-6 text-sm text-muted-foreground">No decisions recorded yet.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={d.by_decision.filter((b) => b.count > 0).map((b) => ({ ...b, label: DECISION_LABEL[b.key] ?? b.key }))}
                  layout="vertical"
                  margin={{ top: 4, right: 40, bottom: 0, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                  <YAxis type="category" dataKey="label" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} width={120} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Cases">
                    {d.by_decision.filter((b) => b.count > 0).map((b) => (
                      <Cell key={b.key} fill={DECISION_COLOR[b.key] ?? 'var(--color-chart-1)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {verifyRate !== null && (
                <p className="mt-3 text-xs text-muted-foreground text-right">
                  Verification rate: <span className="font-medium text-status-clear">{verifyRate}% of decided cases verified</span>
                </p>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
