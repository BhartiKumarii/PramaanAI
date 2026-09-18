import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAnalyticsDashboard } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card, StatTile } from '../components/StatTile'
import { FileText } from 'lucide-react'

const LEVEL_COLOR: Record<string, string> = {
  LOW_RISK: 'var(--color-status-clear)',
  MEDIUM_RISK: 'var(--color-status-review)',
  HIGH_RISK: 'var(--color-status-high)',
}

export function DocumentIntelligence() {
  const analytics = useAsync(() => getAnalyticsDashboard(30), [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Document Intelligence</h1>
        <p className="text-sm text-muted-foreground">
          Real aggregates over every screening this system has scored in the last 30 days — document
          types seen and the risk-level distribution the risk engine actually produced.
        </p>
      </div>

      {analytics.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {analytics.error && <p className="text-sm text-status-high">{analytics.error}</p>}

      {analytics.data && (
        <>
          <StatTile label="Total Screenings (30d)" value={analytics.data.total_screenings} icon={FileText} />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="Document types screened">
              {analytics.data.by_document_type.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={analytics.data.by_document_type}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="key" tick={{ fill: 'var(--color-muted-foreground)', fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fill: 'var(--color-muted-foreground)', fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', fontSize: 12 }}
                    />
                    <Bar dataKey="count" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Risk-level distribution">
              {analytics.data.by_risk_level.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">No screenings yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={analytics.data.by_risk_level}
                      dataKey="count"
                      nameKey="key"
                      innerRadius={50}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {analytics.data.by_risk_level.map((bucket) => (
                        <Cell key={bucket.key} fill={LEVEL_COLOR[bucket.key] ?? 'var(--color-muted-foreground)'} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
              <div className="mt-3 flex flex-wrap justify-center gap-4 text-xs text-muted-foreground">
                {analytics.data.by_risk_level.map((bucket) => (
                  <span key={bucket.key} className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: LEVEL_COLOR[bucket.key] ?? 'var(--color-muted-foreground)' }}
                    />
                    {bucket.key.replace('_', ' ')} ({bucket.count})
                  </span>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
