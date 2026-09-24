import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import logoIcon from '../assets/logo-icon.png'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/console')
    } catch {
      setError('Invalid username or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center text-center">
          <img src={logoIcon} alt="PramaanAI" className="mb-3 h-14 w-14" />
          <h1 className="text-xl font-bold text-foreground">PramaanAI</h1>
        </div>
        <p className="mb-2 text-center text-xs font-medium uppercase tracking-wide text-accent">
          Secure Access
        </p>
        <p className="mb-6 text-center text-sm text-muted-foreground">
          Demo environment &mdash; synthetic accounts only, not connected to any real system.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground" htmlFor="username">
              Officer ID or Email
            </label>
            <input
              id="username"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          {error && <p className="text-sm text-status-high">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {submitting ? 'Signing in…' : 'Log In'}
          </button>
        </form>
        <div className="mt-6 grid grid-cols-3 gap-3">
          <button
            type="button"
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary"
            onClick={() => { setUsername('attari_officer'); setPassword('BorderShield123'); }}
          >
            Attari Officer
          </button>
          <button
            type="button"
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary"
            onClick={() => { setUsername('petrapole_officer'); setPassword('BorderShield123'); }}
          >
            Petrapole Officer
          </button>
          <button
            type="button"
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary"
            onClick={() => { setUsername('admin_reviewer'); setPassword('BorderShield123'); }}
          >
            Admin (reviewer)
          </button>
        </div>
      </div>
    </div>
  )
}