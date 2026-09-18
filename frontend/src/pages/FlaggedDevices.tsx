import { listAdminDevices } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

// A real filter of the existing device list, not a separate tracked
// concept — "flagged" here means disabled but not (yet) revoked; a
// revoked device has its own harder state and its own page.
export function FlaggedDevices() {
  const devices = useAsync(listAdminDevices, [])
  const flagged = devices.data?.filter((d) => d.is_disabled && !d.revoked_at)

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Flagged Devices</h1>
        <p className="text-sm text-muted-foreground">
          Devices disabled by an admin (e.g. reported lost) — a real filter of the device registry, not a
          separately tracked risk score.
        </p>
      </div>

      <Card>
        {devices.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {devices.error && <p className="text-sm text-status-high">{devices.error}</p>}
        {flagged && flagged.length === 0 && <p className="py-6 text-sm text-muted-foreground">No flagged devices.</p>}
        {flagged && flagged.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4">Device ID</th>
                <th className="py-2 pr-4">Officer</th>
                <th className="py-2 pr-4">Last Active</th>
              </tr>
            </thead>
            <tbody>
              {flagged.map((d) => (
                <tr key={d.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-mono text-xs text-foreground">{d.device_identifier}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{d.officer_username ?? '—'}</td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {d.last_active_at ? new Date(d.last_active_at).toLocaleString() : 'Never'}
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
