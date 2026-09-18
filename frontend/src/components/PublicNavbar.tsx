import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import logoIcon from '../assets/logo-icon.png'

const NAV_LINKS = [
  { href: '/', label: 'Home' },
  { href: '/features', label: 'Features' },
  { href: '/how-it-works', label: 'How It Works' },
  { href: '/security', label: 'Security' },
  { href: '/about', label: 'About' },
]

export function PublicNavbar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/95 backdrop-blur-xl">
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-8">
        <div className="flex items-center gap-2.5">
          <img src={logoIcon} alt="PramaanAI" className="h-10 w-10" />
          <span className="text-lg font-semibold tracking-tight text-foreground">PramaanAI</span>
        </div>
        <nav className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <Link key={link.href} to={link.href} className="text-sm text-muted-foreground hover:text-foreground">
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-3 md:flex">
          <Link to="/login" className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary">
            Login
          </Link>
          <Link
            to="/login"
            className="group flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-semibold text-background hover:bg-foreground/90"
          >
            Request Demo
          </Link>
        </div>
        <button className="text-foreground md:hidden" onClick={() => setMobileOpen((v) => !v)} aria-label="Menu">
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>
      <div className={`overflow-hidden transition-all duration-300 md:hidden ${mobileOpen ? 'max-h-64' : 'max-h-0'}`}>
        <div className="flex flex-col gap-4 border-t border-border px-6 py-4">
          {NAV_LINKS.map((link) => (
            <Link key={link.href} to={link.href} className="text-sm text-muted-foreground hover:text-foreground" onClick={() => setMobileOpen(false)}>
              {link.label}
            </Link>
          ))}
          <Link to="/login" className="rounded-md border border-border px-4 py-2 text-center text-sm font-medium text-foreground hover:bg-secondary" onClick={() => setMobileOpen(false)}>
            Login
          </Link>
          <Link to="/login" className="rounded-md bg-foreground px-4 py-2 text-center text-sm font-semibold text-background hover:bg-foreground/90" onClick={() => setMobileOpen(false)}>
            Request Demo
          </Link>
        </div>
      </div>
    </header>
  )
}