import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { AsciiWave } from '../components/decor/AsciiWave'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'

const WORKFLOW_STEPS = [
  {
    number: '01',
    title: 'Capture document details',
    description: 'Officer scans the document and, where applicable, a live photo',
  },
  {
    number: '02',
    title: 'Extract and validate information',
    description: 'OCR, MRZ parsing, and checksum validation happen on the device itself',
  },
  {
    number: '03',
    title: 'Check mock registry',
    description: 'Encoded data only (never a raw image) reaches the server for matching',
  },
  {
    number: '04',
    title: 'Generate explainable result',
    description: 'The system shows exactly which field or check triggered a flag',
  },
  {
    number: '05',
    title: 'Show risk level',
    description: 'Verified, Review Required, or Supervisor Review, never a bare score',
  },
  {
    number: '06',
    title: 'Send flagged cases to supervisor',
    description: 'High-risk results route to a human, automatically',
  },
  {
    number: '07',
    title: 'Authorized officer makes the final decision',
    description: 'The system assists; it never decides',
  },
]

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`animate-in fade-in slide-in-from-bottom-4 duration-700 ${className}`}>{children}</div>
}

export function HowItWorksPage() {
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
            SIH 2026 &middot; Problem Statement 26188
          </span>
          <h1
            className={`mt-6 text-5xl font-semibold leading-[0.95] tracking-tight transition-all delay-100 duration-700 sm:text-7xl ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            From capture to decision, in seconds.
          </h1>
          <p
            className={`mx-auto mt-6 max-w-xl text-lg text-muted-foreground transition-all delay-200 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            Every step happens for a reason &mdash; and every result is explained, not just scored.
          </p>
        </div>
      </section>

      {/* Workflow Steps */}
      <section className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="space-y-8">
            {WORKFLOW_STEPS.map((step, i) => (
              <RevealSection key={step.number} className={`transition-all delay-${i * 80} duration-700`}>
                <div className="flex gap-6">
                  <div className="flex-shrink-0 w-14 text-center">
                    <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-primary font-mono text-lg font-semibold">
                      {step.number}
                    </div>
                    <div className="hidden h-full w-0.5 bg-border mt-2 lg:block" />
                  </div>
                  <div className="flex-1 pt-1">
                    <h3 className="text-lg font-semibold text-foreground">{step.title}</h3>
                    <p className="mt-2 text-muted-foreground">{step.description}</p>
                  </div>
                </div>
              </RevealSection>
            ))}
          </div>

          {/* Closing line */}
          <RevealSection className="mt-16 p-6 rounded-xl border border-border bg-card text-center">
            <p className="text-muted-foreground">
              No step here declares anyone guilty. Every flag is a question for a human, not an answer.
            </p>
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