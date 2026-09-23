import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ShieldCheck,
  FileSearch,
  Fingerprint,
  MapPin,
  Radar,
  UserCog,
  Smartphone,
  BarChart3,
  ScrollText,
  ScanSearch,
  Users,
  Settings,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { useAlertsCount } from '../hooks/useAlertsCount'
import logoIcon from '../assets/logo-icon.png'

const NAV_ICON: Record<string, LucideIcon> = {
  Overview: LayoutDashboard,
  'Verification Desk': ShieldCheck,
  'Document Verification': ScanSearch,
  'Case Intelligence': FileSearch,
  'Identity Intelligence': Fingerprint,
  Checkpoints: MapPin,
  'Area Monitoring': Radar,
  'Officers Monitoring': UserCog,
  'Device Management': Smartphone,
  Users: Users,
  'Analytics & Intelligence': BarChart3,
  'Audit Trail': ScrollText,
  'Admin Settings': Settings,
}

interface NavItem { label: string; to: string; dividerAfter?: boolean }

const NAV_ITEMS: NavItem[] = [
  { label: 'Overview', to: '/console' },
  { label: 'Verification Desk', to: '/console/verification' },
  { label: 'Document Verification', to: '/console/document-verification', dividerAfter: true },
  { label: 'Identity Intelligence', to: '/console/identity' },
  { label: 'Checkpoints', to: '/console/checkpoints' },
  { label: 'Area Monitoring', to: '/console/area-monitoring' },
  { label: 'Officers Monitoring', to: '/console/officers' },
  { label: 'Device Management', to: '/console/devices', dividerAfter: true },
  { label: 'Users', to: '/console/admin/users' },
  { label: 'Analytics & Intelligence', to: '/console/analytics' },
  { label: 'Audit Trail', to: '/console/admin/audit-logs' },
  { label: 'Admin Settings', to: '/console/settings' },
]

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  const alertsCount = useAlertsCount()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300',
        collapsed ? 'w-[72px]' : 'w-[240px]',
      )}
    >
      <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-4">
        <img src={logoIcon} alt="PramaanAI" className="h-8 w-8 shrink-0" />
        <span
          className={cn(
            'overflow-hidden whitespace-nowrap text-sm font-semibold tracking-tight text-sidebar-foreground transition-all duration-300',
            collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100',
          )}
        >
          PramaanAI
        </span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = NAV_ICON[item.label] ?? LayoutDashboard
          const badge = item.label === 'Verification Desk' ? alertsCount : null
          return (
            <div key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/console'}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                      : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && <span className="absolute left-0 h-6 w-1 rounded-r-full bg-accent" />}
                    <Icon
                      className={cn(
                        'h-4.5 w-4.5 shrink-0 transition-transform',
                        isActive ? 'text-accent' : 'group-hover:scale-110',
                      )}
                    />
                    <span
                      className={cn(
                        'flex flex-1 items-center justify-between overflow-hidden whitespace-nowrap transition-all duration-300',
                        collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100',
                      )}
                    >
                      {item.label}
                      {!!badge && badge > 0 && (
                        <span className="ml-2 rounded-full bg-status-high px-1.5 py-0.5 text-[10px] font-semibold text-white">
                          {badge}
                        </span>
                      )}
                    </span>
                  </>
                )}
              </NavLink>
              {item.dividerAfter && (
                <div className={cn('my-2 border-t border-sidebar-border', collapsed ? 'mx-2' : 'mx-3')} />
              )}
            </div>
          )
        })}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <button
          onClick={onToggle}
          className="flex w-full items-center justify-center rounded-lg py-2 text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="h-4.5 w-4.5" /> : <ChevronLeft className="h-4.5 w-4.5" />}
        </button>
      </div>
    </aside>
  )
}
