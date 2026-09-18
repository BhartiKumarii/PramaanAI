import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { AsciiWave } from '../components/decor/AsciiWave'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'

const FEATURES = [
  {
    title: 'OCR document extraction',
    description: 'Reads printed fields directly from the document, on-device',
  },
  {
    title: 'MRZ & checksum validation',
    description: 'Mathematically verifies the document&rsquo;s own internal consistency',
  },
  {
    title: 'Document expiry validation',
    description: 'Flags expired documents automatically, no manual date-checking',
  },
  {
    title: 'Tampering indicators',
    description: 'Surfaces signs of alteration a visual check alone would miss',
  },
  {
    title: 'Identity matching',
    description: 'Compares against previously seen records, not just this one document',
  },
  {
    title: 'Face similarity check',
    description: 'Confirms the person matches their document &mdash; on-device, never storing a raw photo unnecessarily',
  },
  {
    title: 'Duplicate identity indicators',
    description: 'Catches one person appearing under multiple declared identities',
  },
  {
    title: 'Explainable risk results',
    description: 'Every result names the specific field and reason &mdash; never a mystery number',
  },
  {
    title: 'Supervisor review',
    description: 'High-risk cases route to a human automatically, not silently cleared or denied',
  },
  {
    title: 'Audit logs',
    description: 'Every action &mdash; scan, decision, sync &mdash; permanently recorded',
  },
  {
    title: 'Offline sync queue',
    description: 'Works with no connectivity; syncs automatically the moment it returns',
  },
]

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`animate-in fade-in slide-in-from-bottom-4 duration-700 ${className}`}>{children}</div>
}

export function FeaturesPage() {
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
            Built around what actually catches fraud.
          </h1>
          <p
            className={`mx-auto mt-6 max-w-xl text-lg text-muted-foreground transition-all delay-200 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
          >
            Every feature exists because it addresses a real gap at the checkpoint &mdash; not because it looks good on a slide deck.
          </p>
        </div>
      </section>

      {/* Features Table */}
      <section className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-4 font-semibold text-foreground">Feature</th>
                  <th className="text-left p-4 font-semibold text-foreground">Description</th>
                </tr>
              </thead>
              <tbody>
                {FEATURES.map((feature, i) => (
                  <RevealSection key={feature.title} className={`transition-all delay-${i * 30} duration-700`}>
                    <tr className="border-b border-border/50 hover:bg-secondary/30">
                      <td className="p-4 font-medium text-foreground">{feature.title}</td>
                      <td className="p-4 text-muted-foreground">{feature.description}</td>
                    </tr>
                  </RevealSection>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-12 text-center">
            <Link
              to="/how-it-works"
              className="inline-flex items-center gap-2 rounded-md border border-border px-6 py-3 text-sm font-semibold text-foreground hover:bg-secondary"
            >
              See How It Works
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}