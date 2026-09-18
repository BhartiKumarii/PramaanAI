import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAnalyticsDashboard } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card, StatTile } from '../components/StatTile'
import { CheckCircle2, Clock } from 'lucide-react'

const DECISION_LABEL: Record<string, string> = {
  CLEAR: 'Clear',
  MANUAL_REVIEW: 'Manual Review',
}

export function Reports() {
  const analytics = useAsync(() => getAnalyticsDashboard(14), [])

  const clearCount = analytics.data?.by_decision.find((b) => b.key === 'CLEAR')?.count ?? 0
  const reviewCount = analytics.data?.by_decision.find((b) => b.key === 'MANUAL_REVIEW')?.count ?? 0

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Reports & Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Real screening volume and outcome breakdown over the last 14 days — every number here comes
          from a live database query, not a static export.
        </p>
      </div>

      {analytics.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {analytics.error && <p className="text-sm text-status-high">{analytics.error}</p>}

      {analytics.data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <StatTile label="Total Screenings (14d)" value={analytics.data.total_screenings} />
            <StatTile label="Cleared (initial pass)" value={clearCount} accent="clear" icon={CheckCircle2} />
            <StatTile label="Sent to Manual Review" value={reviewCount} accent="review" icon={Clock} />
          </div>

          <Card title="Screening volume, last 14 days">
            {analytics.data.by_day.length === 0 ? (
              <p className="py-6 text-sm text-muted-foreground">No screenings recorded in this window.</p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={analytics.data.by_day}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="key" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', fontSize: 12 }}
                  />
                  <Line type="monotone" dataKey="count" stroke="var(--color-accent)" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="Outcome breakdown">
            {analytics.data.by_decision.length === 0 ? (
              <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={analytics.data.by_decision.map((b) => ({ ...b, label: DECISION_LABEL[b.key] ?? b.key }))}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 12 }} />
                  <YAxis type="category" dataKey="label" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 12 }} width={110} />
                  <Tooltip
                    contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', fontSize: 12 }}
                  />
                  <Bar dataKey="count" fill="var(--color-chart-2)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
