import { useState, useMemo } from 'react'
import { Search, Smartphone, Shield, ShieldOff, ShieldAlert, RefreshCw } from 'lucide-react'
import { listAdminDevices, setDeviceDisabled, revokeDevice, reactivateDevice } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card, StatTile } from '../components/StatTile'
import { ConfirmDialog } from '../components/ConfirmDialog'
import type { AdminDevice } from '../api/types'

type StatusFilter = 'all' | 'active' | 'flagged' | 'revoked'

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

function deviceStatus(d: AdminDevice): 'active' | 'flagged' | 'revoked' {
  if (d.revoked_at) return 'revoked'
  if (d.is_disabled) return 'flagged'
  return 'active'
}

const STATUS_BADGE: Record<string, { label: string; dot: string; text: string; bg: string }> = {
  active: { label: 'Active', dot: 'bg-emerald-400', text: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  flagged: { label: 'Disabled', dot: 'bg-amber-400', text: 'text-amber-400', bg: 'bg-amber-400/10' },
  revoked: { label: 'Revoked', dot: 'bg-red-400', text: 'text-red-400', bg: 'bg-red-400/10' },
}

const FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All Devices' },
  { key: 'active', label: 'Active' },
  { key: 'flagged', label: 'Flagged' },
  { key: 'revoked', label: 'Revoked' },
]

export function DeviceManagement() {
  const devices = useAsync(listAdminDevices, [])
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null)

  const counts = useMemo(() => {
    const list = devices.data ?? []
    return {
      total: list.length,
      active: list.filter((d) => !d.is_disabled && !d.revoked_at).length,
      flagged: list.filter((d) => d.is_disabled && !d.revoked_at).length,
      revoked: list.filter((d) => d.revoked_at).length,
    }
  }, [devices.data])

  const filtered = useMemo(() => {
    let list = devices.data ?? []
    if (filter !== 'all') list = list.filter((d) => deviceStatus(d) === filter)
    const q = search.toLowerCase().trim()
    if (q) {
      list = list.filter(
        (d) =>
          d.device_identifier.toLowerCase().includes(q) ||
          (d.officer_username ?? '').toLowerCase().includes(q),
      )
    }
    return list
  }, [devices.data, filter, search])

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

  async function handleReactivate(id: string) {
    await reactivateDevice(id)
    devices.refetch()
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Device Management</h1>
        <p className="text-sm text-muted-foreground">
          All registered field devices in one view — active, disabled, and revoked. Each action is
          logged to the audit trail.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Total Devices" value={counts.total} icon={Smartphone} delay={0} />
        <StatTile label="Active" value={counts.active} accent="clear" icon={Shield} delay={80} />
        <StatTile label="Disabled" value={counts.flagged} accent="review" icon={ShieldOff} delay={160} />
        <StatTile label="Revoked" value={counts.revoked} accent="high" icon={ShieldAlert} delay={240} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                filter === f.key
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-muted-foreground hover:bg-card hover:text-foreground'
              }`}
            >
              {f.label}
              {f.key !== 'all' && (
                <span className="ml-1.5 text-[10px] opacity-70">
                  {f.key === 'active' ? counts.active : f.key === 'flagged' ? counts.flagged : counts.revoked}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="relative ml-auto min-w-[200px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            className="w-full rounded-md border border-border bg-background py-1.5 pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Search device or officer…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Card>
        {devices.loading && <p className="py-6 text-sm text-muted-foreground">Loading devices…</p>}
        {devices.error && <p className="text-sm text-status-high">{devices.error}</p>}
        {devices.data && filtered.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            {search ? 'No devices match your search.' : 'No devices in this category.'}
          </p>
        )}
        {devices.data && filtered.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2.5 pr-4">Device ID</th>
                  <th className="py-2.5 pr-4">Officer</th>
                  <th className="py-2.5 pr-4">App Version</th>
                  <th className="py-2.5 pr-4">Last Active</th>
                  <th className="py-2.5 pr-4">Status</th>
                  <th className="py-2.5 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => {
                  const status = deviceStatus(d)
                  const badge = STATUS_BADGE[status]
                  return (
                    <tr key={d.id} className="border-b border-border transition-colors hover:bg-secondary/30">
                      <td className="py-2.5 pr-4 font-mono text-xs text-foreground">{d.device_identifier}</td>
                      <td className="py-2.5 pr-4 text-muted-foreground">{d.officer_username ?? '—'}</td>
                      <td className="py-2.5 pr-4 text-muted-foreground">{d.app_version ?? '—'}</td>
                      <td className="py-2.5 pr-4 text-muted-foreground" title={d.last_active_at ?? ''}>
                        {relativeTime(d.last_active_at)}
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
                          {badge.label}
                        </span>
                        {status === 'revoked' && d.revoked_reason && (
                          <p className="mt-0.5 text-[10px] text-muted-foreground" title={d.revoked_reason}>
                            {d.revoked_reason.length > 40 ? d.revoked_reason.slice(0, 40) + '…' : d.revoked_reason}
                          </p>
                        )}
                      </td>
                      <td className="py-2.5 pr-4">
                        <div className="flex gap-2">
                          {status === 'revoked' ? (
                            <button
                              onClick={() => handleReactivate(d.id)}
                              className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary"
                            >
                              <RefreshCw className="h-3 w-3" />
                              Reactivate
                            </button>
                          ) : (
                            <>
                              <button
                                onClick={() => toggle(d.id, d.is_disabled)}
                                className="rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary"
                              >
                                {d.is_disabled ? 'Enable' : 'Disable'}
                              </button>
                              <button
                                onClick={() => setRevokeTarget(d.id)}
                                className="rounded border border-red-400/30 px-2.5 py-1 text-xs font-medium text-red-400 hover:bg-red-400/10"
                              >
                                Revoke
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {revokeTarget && (
        <ConfirmDialog
          title="Revoke device"
          description="A revoked device is permanently disabled until manually reactivated. The reason is logged to the audit trail."
          confirmLabel="Revoke"
          requireReason
          onCancel={() => setRevokeTarget(null)}
          onConfirm={handleRevoke}
        />
      )}
    </div>
  )
}
