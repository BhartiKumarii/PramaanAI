import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FolderOpen,
  Inbox,
  ClipboardCheck,
  AlertTriangle,
  Search,
  Fingerprint,
  Share2,
  ScanText,
  MapPin,
  Radar,
  UserCog,
  Smartphone,
  ShieldAlert,
  Database,
  BarChart3,
  ScrollText,
  Users,
  Activity,
  Settings,
  FlaskConical,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { useAlertsCount } from '../hooks/useAlertsCount'
import logoIcon from '../assets/logo-icon.png'

// Sidebar shape ported from sales-ops-dashboard/components/dashboard/sidebar.tsx:
// fixed-width collapsible aside, icon+label items, absolute left accent bar
// on the active item. All authenticated officers have full access.
const NAV_ICON: Record<string, LucideIcon> = {
  Overview: LayoutDashboard,
  Cases: FolderOpen,
  'Screening Requests': Inbox,
  'Screening Results': ClipboardCheck,
  'Alerts & Review': AlertTriangle,
  'Person Search': Search,
  'Identity Patterns': Fingerprint,
  'Identity Network': Share2,
  'Document Intelligence': ScanText,
  Checkpoints: MapPin,
  'Area Monitoring': Radar,
  'Officers Monitoring': UserCog,
  'Devices Monitoring': Smartphone,
  'Flagged Devices': ShieldAlert,
  'Revoked Devices': ShieldAlert,
  Users: Users,
  Registry: Database,
  'Reports & Analytics': BarChart3,
  'Audit Trail': ScrollText,
  'System Health': Activity,
  'Testing Mode': FlaskConical,
  'Admin Settings': Settings,
}

// Nav list matches the admin-dashboard spec exactly: Overview, Screening
// Requests, Screening Results, Person Search, Identity Network, Document
// Intelligence, Officers Monitoring, Devices Monitoring, Flagged Devices,
// Revoked Devices, Risk and Alerts, Case Management, Area Monitoring,
// System Health, Reports and Analytics, Audit Trail, Admin Settings —
// deliberately no role selector, no per-role dashboard split, no "New
// Screening"/"New Verification" button (screening requests only ever
// come from officer devices, never a web-console button).
const NAV_ITEMS: { label: string; to: string }[] = [
  { label: 'Overview', to: '/console' },
  { label: 'Screening Requests', to: '/console/requests' },
  { label: 'Screening Results', to: '/console/results' },
  { label: 'Case Management', to: '/console/cases' },
  { label: 'Risk & Alerts', to: '/console/alerts' },
  { label: 'Person Search', to: '/console/person-search' },
  { label: 'Identity Patterns', to: '/console/identity-patterns' },
  { label: 'Identity Network', to: '/console/identity-network' },
  { label: 'Document Intelligence', to: '/console/document-intelligence' },
  { label: 'Checkpoints', to: '/console/checkpoints' },
  { label: 'Area Monitoring', to: '/console/area-monitoring' },
  { label: 'Officers Monitoring', to: '/console/officers' },
  { label: 'Devices Monitoring', to: '/console/admin/devices' },
  { label: 'Flagged Devices', to: '/console/devices/flagged' },
  { label: 'Revoked Devices', to: '/console/devices/revoked' },
  { label: 'Users', to: '/console/admin/users' },
  { label: 'Registry', to: '/console/admin/registry' },
  { label: 'System Health', to: '/console/admin/system' },
  { label: 'Reports & Analytics', to: '/console/reports' },
  { label: 'Audit Trail', to: '/console/admin/audit-logs' },
  { label: 'Testing Mode', to: '/console/testing' },
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

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = NAV_ICON[item.label] ?? LayoutDashboard
          const badge = item.label === 'Alerts & Review' ? alertsCount : null
          return (
            <NavLink
              key={item.to}
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
                    {!!badge && (
                      <span className="ml-2 rounded-full bg-status-high px-1.5 py-0.5 text-[10px] font-semibold text-white">
                        {badge}
                      </span>
                    )}
                  </span>
                </>
              )}
            </NavLink>
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