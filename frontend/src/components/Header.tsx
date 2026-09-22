import { useLocation, useNavigate } from 'react-router-dom'
import { Wifi, WifiOff, LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { useHealthPing, type HealthState } from '../hooks/useHealthPing'

const TITLE_BY_PATH: { test: (p: string) => boolean; label: string }[] = [
  { test: (p) => p === '/console', label: 'Overview' },
  { test: (p) => /^\/console\/cases\//.test(p), label: 'Case Intelligence' },
  { test: (p) => p.startsWith('/console/verification'), label: 'Verification Desk' },
  { test: (p) => p.startsWith('/console/cases'), label: 'Verification Desk' },
  { test: (p) => p.startsWith('/console/identity'), label: 'Identity Intelligence' },
  { test: (p) => p.startsWith('/console/document-intelligence'), label: 'Document Intelligence' },
  { test: (p) => p.startsWith('/console/checkpoints'), label: 'Checkpoints' },
  { test: (p) => p.startsWith('/console/area-monitoring'), label: 'Area Monitoring' },
  { test: (p) => p.startsWith('/console/officers'), label: 'Officers Monitoring' },
  { test: (p) => p.startsWith('/console/devices'), label: 'Device Management' },
  { test: (p) => p.startsWith('/console/admin/users'), label: 'User Management' },
  { test: (p) => p.startsWith('/console/admin/audit-logs'), label: 'Audit Trail' },
  { test: (p) => p.startsWith('/console/analytics'), label: 'Analytics & Reports' },
  { test: (p) => p.startsWith('/console/settings'), label: 'Admin Settings' },
]

function sectionTitle(pathname: string): string {
  return TITLE_BY_PATH.find((entry) => entry.test(pathname))?.label ?? 'PramaanAI'
}

export function Header() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const { state: health, everConnected } = useHealthPing()

  if (!user) return null

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const showTag = health !== 'online' && (health !== 'offline' || everConnected)

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur-sm">
      <h1 className="text-lg font-semibold text-foreground">{sectionTitle(location.pathname)}</h1>
      <div className="flex items-center gap-4 text-sm">
        {showTag && (
          <span
            className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] ${
              health === 'checking'
                ? 'border-border text-muted-foreground'
                : health === 'weak'
                  ? 'border-status-review/40 text-status-review'
                  : 'border-status-high/40 text-status-high'
            }`}
            title="Live backend reachability — checked via GET /health"
          >
            {health === 'checking' ? (
              <Wifi className="h-3 w-3 animate-pulse" />
            ) : health === 'weak' ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            {health === 'checking' ? 'Connecting…' : health === 'weak' ? 'Slow' : 'Offline'}
          </span>
        )}
        <span className="hidden text-muted-foreground sm:inline">Officer</span>
        <span className="font-medium text-foreground">{user.username}</span>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-secondary"
        >
          <LogOut className="h-3.5 w-3.5" />
          Log out
        </button>
      </div>
    </header>
  )
}
