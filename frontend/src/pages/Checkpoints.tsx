import { listAdminCheckpoints } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

export function Checkpoints() {
  const checkpoints = useAsync(listAdminCheckpoints, [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Checkpoints</h1>
        <p className="text-sm text-muted-foreground">Every registered checkpoint.</p>
      </div>

      <Card>
        {checkpoints.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {checkpoints.error && <p className="text-sm text-status-high">{checkpoints.error}</p>}
        {checkpoints.data && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4">Code</th>
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Location</th>
                <th className="py-2 pr-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {checkpoints.data.map((cp) => (
                <tr key={cp.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-medium text-foreground">{cp.code}</td>
                  <td className="py-2 pr-4">{cp.name}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{cp.location ?? '—'}</td>
                  <td className="py-2 pr-4">
                    <span className={cp.is_active ? 'text-status-clear' : 'text-status-high'}>
                      {cp.is_active ? 'Active' : 'Inactive'}
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
