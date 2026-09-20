import { useEffect, useState } from 'react'
import { AsciiWave } from '../components/decor/AsciiWave'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'

const INTENDED_USERS = [
  {
    title: 'Field officers',
    description: 'The primary users, working directly with the Android app at checkpoints and on patrol',
  },
  {
    title: 'Supervisors',
    description: 'Oversight, case escalation review, checkpoint monitoring',
  },
  {
    title: 'Administrators',
    description: 'User management, registry maintenance, system health, audit review',
  },
]

const LIMITATIONS = [
  'Registry data is synthetic &mdash; no real government database is connected',
  'Real Aadhaar/biometric API access requires formal government registration, not available at this stage',
  'Some document scripts (e.g., Dzongkha) aren&rsquo;t yet reliably supported by open-source OCR &mdash; this is a named, honest gap, not something claimed as solved',
  'Built and evidence-checked against official SSB sources (ssb.gov.in, mha.gov.in, PIB), not assumptions &mdash; but several operational details (per-checkpoint staffing, exact command structure) remain publicly unconfirmed and are treated as such',
]

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`animate-in fade-in slide-in-from-bottom-4 duration-700 ${className}`}>{children}</div>
}

export function AboutPage() {
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
            PramaanAI &middot; About the Project
          </span>
          <h1
            className={`mt-6 text-5xl font-semibold leading-[0.95] tracking-tight transition-all delay-100 duration-700 sm:text-7xl ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            Why PramaanAI exists.
          </h1>
        </div>
      </section>

      {/* About Content */}
      <section className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-4xl space-y-16">
          {/* Project Purpose */}
          <RevealSection>
            <h2 className="text-2xl font-semibold text-foreground">Project purpose</h2>
            <p className="mt-4 text-muted-foreground">
              PramaanAI is an AI-assisted document and identity verification tool built for a specific, real gap &mdash; SSB&rsquo;s open, treaty-based land borders, where most checkpoints have no server infrastructure and officers currently rely on visual judgement alone.
            </p>
          </RevealSection>

          {/* Problem Addressed */}
          <RevealSection>
            <h2 className="text-2xl font-semibold text-foreground">Problem addressed</h2>
            <p className="mt-4 text-muted-foreground">
              Impersonation and multi-identity fraud at open borders &mdash; not classical passport forgery, which is a different problem at a different kind of border entirely.
            </p>
          </RevealSection>

          {/* Intended Users */}
          <RevealSection>
            <h2 className="text-2xl font-semibold text-foreground">Intended users</h2>
            <div className="mt-6 space-y-4">
              {INTENDED_USERS.map((user, i) => (
                <RevealSection key={user.title} className={`transition-all delay-${i * 60} duration-700`}>
                  <div className="rounded-xl border border-border bg-card p-6">
                    <h3 className="text-lg font-semibold text-foreground">{user.title}</h3>
                    <p className="mt-2 text-muted-foreground">{user.description}</p>
                  </div>
                </RevealSection>
              ))}
            </div>
          </RevealSection>

          {/* Prototype Limitations */}
          <RevealSection>
            <h2 className="text-2xl font-semibold text-foreground">Prototype limitations (stated plainly, not buried)</h2>
            <ul className="mt-6 space-y-3">
              {LIMITATIONS.map((limitation, i) => (
                <RevealSection key={i} className={`transition-all delay-${i * 60} duration-700`}>
                  <li className="flex gap-3 text-muted-foreground">
                    <span className="flex-shrink-0 mt-1 h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                    <span>{limitation}</span>
                  </li>
                </RevealSection>
              ))}
            </ul>
          </RevealSection>
        </div>
      </section>

      <Footer />
    </div>
  )
}