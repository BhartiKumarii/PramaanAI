import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, AlertCircle, WifiOff, Smartphone, Shield, Brain, Zap, Database, Lock, Layers, Users } from 'lucide-react'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'
import { AsciiWave } from '../components/decor/AsciiWave'

const FACT_GRID = [
  { label: 'Countries', value: '2+' },
  { label: 'Border Types', value: 'Land + River' },
  { label: 'Treaty Rights', value: 'Multiple' },
  { label: 'Checkpoints', value: 'Unlimited' },
]

const PROBLEM_POINTS = [
  { icon: AlertCircle, title: 'No Digital Cross-Check', body: 'Officers rely on visual inspection alone — no real-time identity registry or document validation.' },
  { icon: WifiOff, title: 'Infrastructure Gaps', body: 'Many land border crossings lack reliable internet, power, or fixed immigration desks.' },
  { icon: Users, title: 'Multiple Identities', body: 'One person can present different documents at different crossings with no system to detect duplicates.' },
  { icon: Smartphone, title: 'Officer Workload', body: 'High volumes with minimal tooling — every decision is manual, slow, and error-prone.' },
]

const FEATURES = [
  { icon: Brain, title: 'On-Device AI', body: 'OCR, MRZ parsing, face embedding, and tampering checks run locally — no cloud required.' },
  { icon: Zap, title: 'Offline-First', body: 'Full verification workflow works offline. Cases queue and sync when connectivity returns.' },
  { icon: Shield, title: 'Privacy by Design', body: 'No raw biometrics leave the device. Only verification results and hashes are transmitted.' },
  { icon: Database, title: 'Identity Graph', body: 'Cross-checkpoint identity clustering detects multiple documents per person across borders.' },
  { icon: Lock, title: 'Immutable Audit', body: 'Every check creates a tamper-evident log. Supervisors see full history; nothing can be deleted.' },
  { icon: Layers, title: 'Explainable Risk', body: 'LOW/MEDIUM/HIGH with per-signal breakdown — officers see exactly why, not just a score.' },
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
        <div className="relative mx-auto max-w-3xl text-center">
          <span
            className={`inline-block rounded-full border border-border px-3 py-1 font-mono text-xs uppercase tracking-wide text-muted-foreground transition-all duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-2 opacity-0'}`}
          >
            SIH 2026 &middot; Problem Statement 26188
          </span>
          <h1
            className={`mt-6 text-5xl font-semibold leading-[0.95] tracking-tight transition-all delay-100 duration-700 sm:text-7xl ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            Smarter Border Verification. Stronger Identity Security.
          </h1>
          <p
            className={`mx-auto mt-6 max-w-xl text-lg text-muted-foreground transition-all delay-200 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            AI-assisted document verification built for officers at India&rsquo;s open, treaty-based land borders &mdash; where infrastructure is minimal and every check has to count.
          </p>
          <p
            className={`mx-auto mt-4 max-w-xl text-lg text-muted-foreground transition-all delay-200 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            One Android app for the field. One dashboard for everything else. No assumptions about servers that don&rsquo;t exist.
          </p>
          <div
            className={`mt-10 flex flex-wrap items-center justify-center gap-3 transition-all delay-300 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            <Link
              to="/features"
              className="group flex items-center gap-2 rounded-md bg-foreground px-6 py-3 text-sm font-semibold text-background hover:bg-foreground/90"
            >
              Explore Platform
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#how-it-works"
              className="rounded-md border border-border px-6 py-3 text-sm font-semibold text-foreground hover:bg-secondary"
            >
              View Demo
            </a>
          </div>
        </div>

        <div
          className={`relative z-10 mx-auto mt-20 grid w-full max-w-4xl grid-cols-2 gap-px bg-border transition-all delay-500 duration-700 lg:grid-cols-4 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
        >
          {FACT_GRID.map((fact) => (
            <div key={fact.label} className="bg-background p-6 text-center">
              <p className="font-mono text-2xl font-semibold text-foreground">{fact.value}</p>
              <p className="mt-1 text-xs text-muted-foreground">{fact.label}</p>
            </div>
          ))}
        </div>

        <p className="mt-10 mx-auto max-w-xl text-center text-sm text-muted-foreground">
          <span className="font-semibold">A single screen, built around how officers actually work.</span>
        </p>
      </section>

      {/* The Problem */}
      <section id="problem" className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-wide text-accent">// The problem</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              The problem isn&rsquo;t fake passports. It&rsquo;s impersonation.
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm text-muted-foreground">
              At India&rsquo;s open land borders, most travelers cross under treaty rights &mdash; often with minimal documentation and no fixed immigration desk to pass through. The real risk isn&rsquo;t classical passport forgery; it&rsquo;s one person using multiple identities, and officers relying on visual judgement alone, with no digital cross-check and no infrastructure to run one.
            </p>
          </RevealSection>
          <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PROBLEM_POINTS.map(({ icon: PointIcon, title, body }, i) => (
              <RevealSection key={title} className={`card-shadow rounded-xl border border-border bg-card p-5`}>
                <div style={{ animationDelay: `${i * 100}ms` }}>
                  <PointIcon className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{body}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-wide text-accent">// Features</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              Built for the border. Works where infrastructure doesn&rsquo;t.
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm text-muted-foreground">
              Every feature works offline-first. No cloud dependency. No raw biometrics leave the device.
            </p>
          </RevealSection>
          <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: FeatureIcon, title, body }, i) => (
              <RevealSection key={title} className={`card-shadow rounded-xl border border-border bg-card p-6`}>
                <div style={{ animationDelay: `${i * 100}ms` }}>
                  <FeatureIcon className="h-7 w-7 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{body}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-wide text-accent">// How it works</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              From capture to decision in under 30 seconds.
            </h2>
          </RevealSection>
          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { step: '01', title: 'Capture', desc: 'Officer opens Android app, aligns document in green frame. Auto-captures when aligned.' },
              { step: '02', title: 'Selfie', desc: 'Live selfie with random liveness prompt (turn left, blink, nod). On-device face embedding.' },
              { step: '03', title: 'Extract', desc: 'On-device OCR + MRZ parsing. Classical HOG face embedding. Tampering (ELA) check.' },
              { step: '04', title: 'Verify', desc: 'Face match (cosine sim). MRZ checksum. Registry lookup. Identity graph cluster check.' },
              { step: '05', title: 'Score', desc: 'Risk engine computes LOW/MEDIUM/HIGH with per-signal breakdown. Explains exactly why.' },
              { step: '06', title: 'Decide', desc: 'Officer reviews evidence, adds notes, records CLEAR / SECONDARY_REVIEW / HOLD_REFER.' },
              { step: '07', title: 'Sync', desc: 'Case auto-syncs to server. Dashboard updates. Audit trail immutable. Offline queues if needed.' },
              { step: '08', title: 'Monitor', desc: 'Supervisor sees cross-checkpoint analytics. Admin manages officers, devices, registry, health.' },
            ].map(({ step, title, desc }, i) => (
              <RevealSection key={step} className={`card-shadow rounded-xl border border-border bg-card p-5`}>
                <div style={{ animationDelay: `${i * 100}ms` }}>
                  <p className="font-mono text-xs uppercase tracking-wide text-accent">{step}</p>
                  <h3 className="mt-2 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}