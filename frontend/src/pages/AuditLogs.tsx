import { listAuditLogs } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

export function AuditLogs() {
  const logs = useAsync(() => listAuditLogs(200), [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Audit Logs</h1>
        <p className="text-sm text-muted-foreground">Every logged system event — read-only, most recent first.</p>
      </div>

      <Card>
        {logs.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {logs.error && <p className="text-sm text-status-high">{logs.error}</p>}
        {logs.data && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4">Timestamp</th>
                  <th className="py-2 pr-4">User</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Action</th>
                  <th className="py-2 pr-4">Case</th>
                  <th className="py-2 pr-4">Reason</th>
                </tr>
              </thead>
              <tbody>
                {logs.data.map((entry) => (
                  <tr key={entry.id} className="border-b border-border">
                    <td className="py-2 pr-4 text-muted-foreground">{new Date(entry.created_at).toLocaleString()}</td>
                    <td className="py-2 pr-4 font-medium text-foreground">{entry.actor_username ?? 'unknown'}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{entry.actor_role?.replace('_', ' ') ?? '—'}</td>
                    <td className="py-2 pr-4">{entry.event_type}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{entry.case_number ?? '—'}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{entry.reason ?? '—'}</td>
                  </tr>
                ))}
                {logs.data.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-muted-foreground">
                      No events logged yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
