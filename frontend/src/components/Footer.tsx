import { Link } from 'react-router-dom'
import logoIcon from '../assets/logo-icon.png'

export function Footer() {
  return (
    <footer className="border-t border-border px-6 py-10 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 text-center">
        <div className="flex items-center gap-2">
          <img src={logoIcon} alt="PramaanAI" className="h-5 w-5" />
          <span className="text-sm font-semibold text-foreground">PramaanAI</span>
        </div>
        <p className="text-xs text-muted-foreground">AI-assisted identity and document verification designed for real-world border and checkpoint operations.</p>
        <p className="text-xs text-muted-foreground">
          Prototype build &mdash; uses synthetic data only. Not connected to any real government database.
        </p>
        <nav className="mt-4 flex flex-wrap items-center justify-center gap-4 text-xs text-muted-foreground">
          <Link to="/features" className="hover:text-foreground">Features</Link>
          <Link to="/how-it-works" className="hover:text-foreground">How It Works</Link>
          <Link to="/security" className="hover:text-foreground">Security</Link>
          <Link to="/about" className="hover:text-foreground">About</Link>
        </nav>
      </div>
    </footer>
  )
}