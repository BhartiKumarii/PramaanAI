import { listOfficers } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

export function Officers() {
  const officers = useAsync(listOfficers, [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Officers</h1>
        <p className="text-sm text-muted-foreground">
          Field and Immigration officers, with a real case count each.
        </p>
      </div>

      <Card>
        {officers.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {officers.error && <p className="text-sm text-status-high">{officers.error}</p>}
        {officers.data && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4">Username</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Checkpoint</th>
                <th className="py-2 pr-4">Cases Submitted</th>
                <th className="py-2 pr-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {officers.data.map((o) => (
                <tr key={o.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-medium text-foreground">{o.username}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{o.role.replace('_', ' ')}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{o.checkpoint_code ?? '—'}</td>
                  <td className="py-2 pr-4 text-foreground">{o.case_count}</td>
                  <td className="py-2 pr-4">
                    <span className={o.is_active ? 'text-status-clear' : 'text-status-high'}>
                      {o.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
