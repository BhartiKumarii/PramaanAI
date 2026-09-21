import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { AsciiWave } from '../components/decor/AsciiWave'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'

const WORKFLOW_STEPS = [
  {
    number: '01',
    title: 'Capture',
    description: 'Officer photographs the document front, back (optional), and takes a live selfie through the Android app.',
  },
  {
    number: '02',
    title: 'On-device processing',
    description: 'OCR, MRZ parsing, document type detection, image quality checks, face detection and preliminary analysis all happen on the device — no network required.',
  },
  {
    number: '03',
    title: 'Local cache check',
    description: 'The app checks if this document or identity has been verified before, showing the cached result with its age and a "refresh recommended" flag if stale.',
  },
  {
    number: '04',
    title: 'Connectivity check',
    description: 'A live health check determines whether the server is reachable right now — online, weak, or offline. Never assumed, always measured.',
  },
  {
    number: '05',
    title: 'Secure data transmission',
    description: 'Only encoded data (OCR fields, MRZ string, face embedding vector) is sent encrypted to the server. Raw document and selfie images never leave the device.',
  },
  {
    number: '06',
    title: 'Server verification',
    description: 'Registry matching, identity graph analysis, cross-field validation, tampering indicators, face comparison and risk scoring run on the central server.',
  },
  {
    number: '07',
    title: 'Explainable result',
    description: 'The system returns Verified, Review Required, or Flagged — along with the exact checks and fields that triggered each finding. No bare score, no mystery number.',
  },
  {
    number: '08',
    title: 'Officer decision',
    description: 'The officer reviews the evidence and makes the final operational decision using their own judgment and procedure. The system assists — it never declares guilt or denies entry.',
  },
  {
    number: '09',
    title: 'Synchronization and audit',
    description: 'If offline, encrypted cases queue locally and sync automatically when connectivity returns. Every action is recorded in a tamper-evident audit trail.',
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
            PramaanAI &middot; System Workflow
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