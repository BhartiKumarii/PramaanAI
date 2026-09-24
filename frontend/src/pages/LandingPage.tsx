import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ShieldCheck,
  ScanSearch,
  ShieldAlert,
  UserCheck,
  Eye,
  Landmark,
  LayoutDashboard,
  FileCheck,
  Network,
  KeyRound,
  Lock,
  ScrollText,
  Users,
  ChevronDown,
} from 'lucide-react'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'
import { AsciiWave } from '../components/decor/AsciiWave'
import { ParticleLock } from '../components/decor/ParticleLock'

const CAPABILITIES = [
  { icon: ScanSearch, title: 'Reads every border document', desc: 'Passports, visas, permits, licences, Aadhaar and stamps, in English, Hindi and Nepali.' },
  { icon: ShieldAlert, title: 'Spots inconsistencies', desc: 'MRZ digits, dates, stamps, QR signatures and altered regions, checked in seconds.' },
  { icon: UserCheck, title: 'Confirms the person', desc: 'Face match with a live photo, plus blink and head-turn liveness.' },
  { icon: Landmark, title: 'Border-aware rules', desc: 'India–Nepal and India–Bhutan crossing rules applied to every result.' },
  { icon: Eye, title: 'Explains every flag', desc: 'Named reasons, marked on the document itself. Never a mystery score.' },
  { icon: Users, title: 'The officer decides', desc: 'Clear, or send to an admin, who answers with evidence in view.' },
]

const STEPS = [
  { step: '01', title: 'Capture', desc: 'Photograph the document and the traveller.' },
  { step: '02', title: 'Check', desc: 'The phone and server run every check.' },
  { step: '03', title: 'Explain', desc: 'See what passed, what didn’t, and where.' },
  { step: '04', title: 'Decide', desc: 'Clear, or send to an admin for review.' },
]

const PILLARS = [
  { icon: LayoutDashboard, title: 'Command oversight', desc: 'Admins review every case sent from the field — document, live photo, findings and a suggested action — and every decision is logged.' },
  { icon: FileCheck, title: 'Evidence you can defend', desc: 'Each result names the check, marks the exact spot on the document and is sealed in a tamper-evident record.' },
  { icon: Network, title: 'Ready to integrate', desc: 'Every check is a separate service, ready to connect to authorised government systems without changing the app.' },
]

const TRUST = [
  { icon: KeyRound, title: 'Role-based access', desc: 'Enforced on the server' },
  { icon: Lock, title: 'Encrypted', desc: 'In transit and on the device' },
  { icon: ScrollText, title: 'Tamper-evident audit', desc: 'Every action recorded' },
  { icon: ShieldCheck, title: 'Privacy by design', desc: 'Only needed regions leave the phone' },
]

const FACTS = [
  { value: '2', label: 'open borders: Nepal and Bhutan' },
  { value: '10+', label: 'document types' },
  { value: '7', label: 'app languages' },
  { value: 'Every', label: 'flag explained' },
]

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`animate-in fade-in slide-in-from-bottom-4 duration-700 ${className}`}>{children}</div>
}

export function LandingPage() {
  const [heroVisible, setHeroVisible] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setHeroVisible(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <div className="theme-landing relative min-h-screen overflow-x-hidden bg-background text-foreground">
      <PublicNavbar />

      {/* Hero */}
      <section className="relative flex min-h-screen flex-col justify-center overflow-hidden px-6 pt-20 lg:px-8">
        <div className="grid-pattern absolute inset-0" />
        <AsciiWave className="pointer-events-none absolute inset-0 h-full w-full opacity-20" />
        <div className="relative mx-auto grid w-full max-w-6xl items-center gap-12 lg:grid-cols-[1fr_auto]">
          {/* Left — text content */}
          <div className="text-left">
            <div
              className={`inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/5 px-4 py-1.5 font-mono text-xs uppercase tracking-wider text-accent transition-all duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-2 opacity-0'}`}
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              Secure &middot; Explainable &middot; Officer-led
            </div>
            <h1
              className={`mt-8 text-4xl font-semibold leading-[1.1] tracking-tight transition-all delay-100 duration-700 sm:text-5xl lg:text-6xl ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              Verify the document. Confirm the person.
            </h1>
            <p
              className={`mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground transition-all delay-200 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              AI-assisted identity and document checks for SSB officers on the India–Nepal and India–Bhutan borders.
            </p>
            <p
              className={`mt-4 max-w-2xl text-base text-muted-foreground/80 transition-all delay-250 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              Every flag explained. Every decision the officer&apos;s.
            </p>
            <div
              className={`mt-10 flex flex-wrap items-center gap-4 transition-all delay-300 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              <Link
                to="/features"
                className="group flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-background hover:bg-accent/90 transition-colors"
              >
                Explore the Platform
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#how"
                className="flex items-center gap-2 rounded-lg border border-border px-6 py-3 text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
              >
                How it works
                <ChevronDown className="h-4 w-4" />
              </a>
            </div>
          </div>

          {/* Right — particle padlock (canvas, blends into the background) */}
          <div
            className={`flex items-center justify-center transition-opacity delay-300 duration-1000 ${heroVisible ? 'opacity-100' : 'opacity-0'}`}
          >
            <ParticleLock className="h-72 w-72 sm:h-96 sm:w-96 lg:h-[26rem] lg:w-[26rem]" />
          </div>
        </div>
      </section>

      {/* Problem */}
      <section id="problem" className="bg-secondary/30 px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <RevealSection>
            <p className="font-mono text-xs uppercase tracking-widest text-accent">The challenge</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Open borders. Real impersonation risk.
            </h2>
            <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground">
              Most crossers carry no passport, posts often have no network, and checks are done by eye. PramaanAI puts
              every check in the officer&apos;s hand.
            </p>
          </RevealSection>
        </div>
      </section>

      {/* What it does */}
      <section id="features" className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">What it does</h2>
          </RevealSection>
          <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map(({ icon: Icon, title, desc }, i) => (
              <RevealSection key={title}>
                <div className="group h-full rounded-xl border border-border bg-card p-6 transition-colors hover:border-accent/30" style={{ animationDelay: `${i * 80}ms` }}>
                  <Icon className="h-7 w-7 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-4 text-base font-semibold text-foreground">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="bg-secondary/30 px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <RevealSection className="text-center">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">How it works</h2>
          </RevealSection>
          <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ step, title, desc }) => (
              <RevealSection key={step}>
                <div className="h-full rounded-xl border border-border bg-card p-6">
                  <p className="font-mono text-xs font-bold uppercase tracking-widest text-accent">{step}</p>
                  <h3 className="mt-3 text-base font-semibold text-foreground">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Built for SSB operations */}
      <section className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Built for SSB operations</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">From the post to command</h2>
          </RevealSection>
          <div className="mt-12 grid grid-cols-1 gap-5 lg:grid-cols-3">
            {PILLARS.map(({ icon: Icon, title, desc }) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-border bg-card p-7">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-accent/30 bg-accent/10">
                    <Icon className="h-5 w-5 text-accent" strokeWidth={1.75} />
                  </div>
                  <h3 className="mt-5 text-lg font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Trust and security */}
      <section className="bg-secondary/30 px-6 py-16 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Trust and security, built in</h2>
          </RevealSection>
          <div className="mt-10 grid grid-cols-2 gap-5 lg:grid-cols-4">
            {TRUST.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3 rounded-xl border border-border bg-card p-5">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-accent" strokeWidth={1.75} />
                <div>
                  <p className="text-sm font-semibold text-foreground">{title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Facts */}
      <section className="px-6 py-16 lg:px-8">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-6 text-center lg:grid-cols-4">
          {FACTS.map(({ value, label }) => (
            <div key={label}>
              <p className="text-3xl font-semibold tracking-tight text-accent sm:text-4xl">{value}</p>
              <p className="mt-1 text-sm text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <RevealSection>
            <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">PramaanAI</h2>
            <div className="mt-6 space-y-1 text-lg text-muted-foreground">
              <p>Verify the document.</p>
              <p>Confirm the person.</p>
              <p>Let the officer decide.</p>
            </div>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Link
                to="/features"
                className="group flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-background hover:bg-accent/90 transition-colors"
              >
                Explore PramaanAI
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link
                to="/how-it-works"
                className="rounded-lg border border-border px-6 py-3 text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
              >
                See How It Works
              </Link>
            </div>
          </RevealSection>
        </div>
      </section>

      <Footer />
    </div>
  )
}
