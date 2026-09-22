import { useLocation, useNavigate } from 'react-router-dom'
import { Wifi, WifiOff, LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { useHealthPing } from '../hooks/useHealthPing'

const TITLE_BY_PATH: { test: (p: string) => boolean; label: string }[] = [
  { test: (p) => p === '/console', label: 'Overview' },
  { test: (p) => p.startsWith('/console/requests'), label: 'Screening Requests' },
  { test: (p) => p.startsWith('/console/results'), label: 'Screening Results' },
  { test: (p) => p.startsWith('/console/cases'), label: 'Case Management' },
  { test: (p) => p.startsWith('/console/alerts'), label: 'Risk & Alerts' },
  { test: (p) => p.startsWith('/console/person-search'), label: 'Person Search' },
  { test: (p) => p.startsWith('/console/identity-patterns'), label: 'Identity & Pattern Analysis' },
  { test: (p) => p.startsWith('/console/identity-network'), label: 'Identity Network' },
  { test: (p) => p.startsWith('/console/document-intelligence'), label: 'Document Intelligence' },
  { test: (p) => p.startsWith('/console/checkpoints'), label: 'Checkpoints' },
  { test: (p) => p.startsWith('/console/area-monitoring'), label: 'Area Monitoring' },
  { test: (p) => p.startsWith('/console/officers'), label: 'Officers Monitoring' },
  { test: (p) => p.startsWith('/console/devices/flagged'), label: 'Flagged Devices' },
  { test: (p) => p.startsWith('/console/devices/revoked'), label: 'Revoked Devices' },
  { test: (p) => p.startsWith('/console/admin/users'), label: 'User Management' },
  { test: (p) => p.startsWith('/console/admin/devices'), label: 'Devices Monitoring' },
  { test: (p) => p.startsWith('/console/admin/registry'), label: 'Registry' },
  { test: (p) => p.startsWith('/console/admin/system'), label: 'System Health' },
  { test: (p) => p.startsWith('/console/admin/audit-logs'), label: 'Audit Trail' },
  { test: (p) => p.startsWith('/console/reports'), label: 'Reports & Analytics' },
  { test: (p) => p.startsWith('/console/settings'), label: 'Admin Settings' },
]

function sectionTitle(pathname: string): string {
  return TITLE_BY_PATH.find((entry) => entry.test(pathname))?.label ?? 'PramaanAI'
}

export function Header() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const health = useHealthPing()

  if (!user) return null

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur-sm">
      <h1 className="text-lg font-semibold text-foreground">{sectionTitle(location.pathname)}</h1>
      <div className="flex items-center gap-4 text-sm">
        {health !== 'online' && (
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
