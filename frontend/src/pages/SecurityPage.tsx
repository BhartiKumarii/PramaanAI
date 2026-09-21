import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ShieldCheck } from 'lucide-react'
import { AsciiWave } from '../components/decor/AsciiWave'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'

const SECURITY_ITEMS = [
  {
    title: 'Data minimization',
    description: 'Raw document and selfie images stay on the capturing device wherever the workflow supports it; only small encoded data (text fields, MRZ string, face data) ever reaches the server.',
  },
  {
    title: 'HTTPS/TLS',
    description: 'Every request is encrypted in transit, including on local networks.',
  },
  {
    title: 'Encryption at rest',
    description: 'Locally cached and offline-queued cases are encrypted, not stored as plain text.',
  },
  {
    title: 'Role-based access control',
    description: 'Enforced server-side. A hidden button in the UI is not a permission boundary.',
  },
  {
    title: 'Audit logs',
    description: 'Every action is permanently recorded &mdash; login, scan, decision, sync &mdash; addressing a documented real-world failure pattern where fraud information often goes unrecorded in manual processes.',
  },
  {
    title: 'Synthetic mock registry',
    description: 'All registry data in this build is synthetic. No real government database is connected.',
  },
  {
    title: 'Human-in-the-loop decisions',
    description: 'The system never auto-declares a verdict. Every flagged case goes to a person.',
  },
  {
    title: 'Approved infrastructure requirement',
    description: 'A real deployment requires authorized government infrastructure, approved APIs, and formal data-access permissions.',
  },
]

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`animate-in fade-in slide-in-from-bottom-4 duration-700 ${className}`}>{children}</div>
}

export function SecurityPage() {
  const [heroVisible, setHeroVisible] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setHeroVisible(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <div className="theme-landing relative min-h-screen overflow-x-hidden bg-background text-foreground">
      <PublicNavbar />

      {/* Hero */}
      <section className="relative flex min-h-[60vh] flex-col justify-center overflow-hidden px-6 pt-20 lg:px-8">
        <div className="grid-pattern absolute inset-0" />
        <AsciiWave className="pointer-events-none absolute inset-0 h-full w-full opacity-20" />
        <div className="relative mx-auto max-w-3xl text-center">
          <span
            className={`inline-block rounded-full border border-border px-3 py-1 font-mono text-xs uppercase tracking-wide text-muted-foreground transition-all duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-2 opacity-0'}`}
          >
            PramaanAI &middot; Security Architecture
          </span>
          <h1
            className={`mt-6 text-5xl font-semibold leading-[0.95] tracking-tight transition-all delay-100 duration-700 sm:text-7xl ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            Data stays minimal. Access stays controlled.
          </h1>
        </div>
      </section>

      {/* Security Items */}
      <section className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="space-y-6">
            {SECURITY_ITEMS.map((item, i) => (
              <RevealSection key={item.title} className={`transition-all delay-${i * 60} duration-700`}>
                <div className="rounded-xl border border-border bg-card p-6">
                  <h3 className="text-lg font-semibold text-foreground">{item.title}</h3>
                  <p className="mt-2 text-muted-foreground">{item.description}</p>
                </div>
              </RevealSection>
            ))}
          </div>

          {/* Prominent callout box */}
          <RevealSection className="mt-12 p-6 rounded-xl border-2 border-accent/50 bg-accent/10">
            <div className="flex gap-4">
              <ShieldCheck className="h-6 w-6 text-accent shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <p className="font-semibold text-foreground">Prototype uses synthetic/mock registry data.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Real deployment requires authorized government infrastructure, approved APIs, and formal data-access permissions.
                </p>
              </div>
            </div>
          </RevealSection>

          <div className="mt-12 text-center">
            <Link
              to="/features"
              className="inline-flex items-center gap-2 rounded-md border border-border px-6 py-3 text-sm font-semibold text-foreground hover:bg-secondary"
            >
              View Features
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}