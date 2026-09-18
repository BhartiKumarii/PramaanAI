import { useState } from 'react'
import { listAdminDevices, revokeDevice, setDeviceDisabled } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'
import { ConfirmDialog } from '../components/ConfirmDialog'

export function AdminDevices() {
  const devices = useAsync(listAdminDevices, [])
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null)

  async function toggle(deviceId: string, isDisabled: boolean) {
    await setDeviceDisabled(deviceId, !isDisabled)
    devices.refetch()
  }

  async function handleRevoke(reason: string) {
    if (!revokeTarget || !reason.trim()) return
    await revokeDevice(revokeTarget, reason.trim())
    setRevokeTarget(null)
    devices.refetch()
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Devices Monitoring</h1>
        <p className="text-sm text-muted-foreground">
          Every registered device, with disable/re-enable and revoke control.
        </p>
      </div>
      <Card>
        {devices.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {devices.error && <p className="text-sm text-status-high">{devices.error}</p>}
        {devices.data && devices.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No devices have registered yet.</p>
        )}
        {devices.data && devices.data.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4">Device ID</th>
                <th className="py-2 pr-4">Officer</th>
                <th className="py-2 pr-4">App Version</th>
                <th className="py-2 pr-4">Last Active</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {devices.data.map((d) => (
                <tr key={d.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-mono text-xs text-foreground">{d.device_identifier}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{d.officer_username ?? '—'}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{d.app_version ?? '—'}</td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {d.last_active_at ? new Date(d.last_active_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="py-2 pr-4">
                    {d.revoked_at ? (
                      <span className="text-status-high">Revoked</span>
                    ) : (
                      <span className={d.is_disabled ? 'text-status-high' : 'text-status-clear'}>
                        {d.is_disabled ? 'Disabled' : 'Active'}
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <div className="flex gap-2">
                      {!d.revoked_at && (
                        <button
                          onClick={() => toggle(d.id, d.is_disabled)}
                          className="rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary"
                        >
                          {d.is_disabled ? 'Re-enable' : 'Disable'}
                        </button>
                      )}
                      {!d.revoked_at && (
                        <button
                          onClick={() => setRevokeTarget(d.id)}
                          className="rounded border border-status-high/40 px-2.5 py-1 text-xs font-medium text-status-high hover:bg-status-high-bg"
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {revokeTarget && (
        <ConfirmDialog
          title="Revoke device"
          description="A revoked device is a harder, reasoned state than disabling — it stays in the Revoked Devices list until reactivated, and the reason is logged permanently."
          confirmLabel="Revoke"
          requireReason
          onCancel={() => setRevokeTarget(null)}
          onConfirm={handleRevoke}
        />
      )}
    </div>
  )
}
