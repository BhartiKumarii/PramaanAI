import { getSyncStatus, getSystemHealth } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card, StatTile } from '../components/StatTile'

export function AdminSystem() {
  const health = useAsync(getSystemHealth, [])
  const sync = useAsync(getSyncStatus, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">System Health &amp; Sync</h1>

      <Card title="Component Health">
        {health.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {health.error && <p className="text-sm text-status-high">{health.error}</p>}
        {health.data && (
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">API</dt>
              <dd className="text-sm font-medium text-status-clear">{health.data.api_status}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Database</dt>
              <dd
                className={`text-sm font-medium ${health.data.database_status === 'ok' ? 'text-status-clear' : 'text-status-high'}`}
              >
                {health.data.database_status}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Analysis Pipeline</dt>
              <dd className="text-sm font-medium text-foreground">{health.data.analysis_pipeline_status}</dd>
            </div>
          </dl>
        )}
        {health.data && (
          <p className="mt-3 text-xs text-muted-foreground">Checked {new Date(health.data.checked_at).toLocaleString()}</p>
        )}
      </Card>

      <Card title="Offline Sync Queue">
        {sync.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {sync.error && <p className="text-sm text-status-high">{sync.error}</p>}
        {sync.data && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Pending" value={sync.data.pending} accent="review" />
            <StatTile label="Synced" value={sync.data.synced} accent="clear" />
            <StatTile label="Failed" value={sync.data.failed} accent="high" />
            <StatTile
              label="Last Successful Sync"
              value={sync.data.last_successful_sync_at ? new Date(sync.data.last_successful_sync_at).toLocaleString() : 'Never'}
            />
          </div>
        )}
      </Card>
    </div>
  )
}
