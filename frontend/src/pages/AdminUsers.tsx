import { useState } from 'react'
import { createAdminUser, listAdminCheckpoints, listAdminUsers, updateAdminUser } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

export function AdminUsers() {
  const users = useAsync(listAdminUsers, [])
  const checkpoints = useAsync(listAdminCheckpoints, [])
  const [form, setForm] = useState({ username: '', password: '', checkpoint_id: '' })
  const [error, setError] = useState<string | null>(null)

  async function handleCreate() {
    setError(null)
    try {
      await createAdminUser({
        username: form.username,
        password: form.password,
        role: 'OFFICER',
        checkpoint_id: form.checkpoint_id || null,
      })
      setForm({ username: '', password: '', checkpoint_id: '' })
      users.refetch()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not create user.')
    }
  }

  async function toggleActive(userId: string, isActive: boolean) {
    await updateAdminUser(userId, { is_active: !isActive })
    users.refetch()
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">User Management</h1>

      <Card title="Add User">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input
            className="rounded-md border border-border px-3 py-2 text-sm"
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <input
            className="rounded-md border border-border px-3 py-2 text-sm"
            placeholder="Password"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <select
            className="rounded-md border border-border px-3 py-2 text-sm"
            value={form.checkpoint_id}
            onChange={(e) => setForm({ ...form, checkpoint_id: e.target.value })}
          >
            <option value="">No checkpoint</option>
            {checkpoints.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
        </div>
        {checkpoints.error && <p className="mt-2 text-xs text-status-high">{checkpoints.error}</p>}
        {error && <p className="mt-2 text-xs text-status-high">{error}</p>}
        <button
          onClick={handleCreate}
          className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        >
          Create User
        </button>
      </Card>

      <Card title="All Users">
        {users.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {users.error && <p className="text-sm text-status-high">{users.error}</p>}
        {users.data && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4">Username</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Checkpoint</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <tr key={u.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-medium text-foreground">{u.username}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{u.role}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{u.checkpoint_code ?? '—'}</td>
                  <td className="py-2 pr-4">
                    <span className={u.is_active ? 'text-status-clear' : 'text-status-high'}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => toggleActive(u.id, u.is_active)}
                      className="rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary"
                    >
                      {u.is_active ? 'Disable' : 'Enable'}
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
