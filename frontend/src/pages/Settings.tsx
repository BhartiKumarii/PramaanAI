import { getRiskConfig } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

export function Settings() {
  const config = useAsync(getRiskConfig, [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Admin Settings</h1>
        <p className="text-sm text-muted-foreground">
          The real active risk-scoring configuration — read-only. There's no persistence layer for this
          yet, so this shows exactly what the risk engine is actually using, not an editable store.
        </p>
      </div>

      {config.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {config.error && <p className="text-sm text-status-high">{config.error}</p>}

      {config.data && (
        <>
          <Card title="Signal weights">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4">Signal</th>
                  <th className="py-2 pr-4">Weight</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(config.data.weights).map(([signal, weight]) => (
                  <tr key={signal} className="border-b border-border">
                    <td className="py-2 pr-4 font-medium text-foreground">{signal.replace('_', ' ')}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted-foreground">
              A missing signal has its weight dropped and the rest renormalized — never treated as zero
              risk.
            </p>
          </Card>

          <Card title="Risk-level thresholds">
            <div className="flex gap-6 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Low risk ceiling</p>
                <p className="mt-1 font-medium text-status-clear">{config.data.low_risk_ceiling}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Medium risk ceiling</p>
                <p className="mt-1 font-medium text-status-review">{config.data.medium_risk_ceiling}</p>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
