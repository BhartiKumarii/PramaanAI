import { listAdminDevices, reactivateDevice } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

export function RevokedDevices() {
  const devices = useAsync(listAdminDevices, [])
  const revoked = devices.data?.filter((d) => d.revoked_at)

  async function reactivate(id: string) {
    await reactivateDevice(id)
    devices.refetch()
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Revoked Devices</h1>
        <p className="text-sm text-muted-foreground">
          Devices revoked through the confirm-and-reason workflow (see Devices Monitoring). Each revoke
          is logged to the audit trail.
        </p>
      </div>

      <Card>
        {devices.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {devices.error && <p className="text-sm text-status-high">{devices.error}</p>}
        {revoked && revoked.length === 0 && <p className="py-6 text-sm text-muted-foreground">No revoked devices.</p>}
        {revoked && revoked.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4">Device ID</th>
                <th className="py-2 pr-4">Officer</th>
                <th className="py-2 pr-4">Revoked At</th>
                <th className="py-2 pr-4">Reason</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {revoked.map((d) => (
                <tr key={d.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-mono text-xs text-foreground">{d.device_identifier}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{d.officer_username ?? '—'}</td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {d.revoked_at ? new Date(d.revoked_at).toLocaleString() : '—'}
                  </td>
                  <td className="py-2 pr-4 text-foreground">{d.revoked_reason ?? '—'}</td>
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => reactivate(d.id)}
                      className="rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary"
                    >
                      Reactivate
                    </button>
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
