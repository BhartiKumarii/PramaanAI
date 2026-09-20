import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ShieldCheck,
  Fingerprint,
  ScanSearch,
  UserCheck,
  Users,
  AlertTriangle,
  Wifi,
  WifiOff,
  Signal,
  RefreshCw,
  Lock,
  Eye,
  Server,
  KeyRound,
  FileCheck,
  ShieldAlert,
  BarChart3,
  ClipboardList,
  FileWarning,
  ScrollText,
  UserCog,
  Smartphone,
  Globe,
  Database,
  Scale,
  Satellite,
  Cctv,
  Network,
  Languages,
  CheckCircle2,
  CircleDot,
  HelpCircle,
  MonitorSmartphone,
  LayoutDashboard,
  ChevronDown,
} from 'lucide-react'
import { PublicNavbar } from '../components/PublicNavbar'
import { Footer } from '../components/Footer'
import { AsciiWave } from '../components/decor/AsciiWave'
import logoIcon from '../assets/logo-icon.png'

const VERIFICATION_SIGNALS = [
  {
    icon: ScanSearch,
    title: 'Document Intelligence',
    body: 'Extract and validate relevant information from identity and travel documents using OCR and document-aware processing.',
  },
  {
    icon: ShieldAlert,
    title: 'Tampering Detection',
    body: 'Identify potential alterations such as modified photographs, dates of birth, document numbers, stamps, text, or other visual inconsistencies.',
  },
  {
    icon: Fingerprint,
    title: 'Identity Verification',
    body: 'Compare extracted identity information against available verification sources and identify inconsistencies.',
  },
  {
    icon: UserCheck,
    title: 'Face–Document Verification',
    body: 'Compare the person presented at the checkpoint with the photograph associated with the document.',
  },
  {
    icon: Users,
    title: 'Multiple Identity Detection',
    body: 'Identify conflicting identity records or the association of different documents with the same person for further officer review.',
  },
  {
    icon: BarChart3,
    title: 'Risk-Based Assessment',
    body: 'Convert verification signals into an understandable result with supporting reasons.',
  },
]

const WORKFLOW_STEPS = [
  { step: '01', title: 'Capture', desc: 'The officer captures the identity or travel document through the mobile application.' },
  { step: '02', title: 'On-Device Processing', desc: 'Initial image processing and required preprocessing take place on the officer’s device before transmission.' },
  { step: '03', title: 'Secure Verification', desc: 'Required information is securely transmitted to the central verification system when connectivity is available.' },
  { step: '04', title: 'Multi-Level Analysis', desc: 'PramaanAI performs document validation, tampering analysis, identity matching, face comparison, and other configured checks.' },
  { step: '05', title: 'Explainable Result', desc: 'The system presents a clear verification status together with the signals that contributed to it.' },
  { step: '06', title: 'Human Decision', desc: 'The officer remains responsible for the final action. PramaanAI supports the decision; it does not replace the officer.' },
]

const RISK_LEVELS = [
  { level: 'LOW', color: 'text-emerald-400', bg: 'bg-emerald-400/10 border-emerald-400/20', icon: CheckCircle2, desc: 'No significant verification issue detected.' },
  { level: 'MEDIUM', color: 'text-amber-400', bg: 'bg-amber-400/10 border-amber-400/20', icon: CircleDot, label: 'Needs Review', desc: 'A mismatch, uncertainty, or potential anomaly requires additional officer attention.' },
  { level: 'HIGH', color: 'text-red-400', bg: 'bg-red-400/10 border-red-400/20', icon: AlertTriangle, label: 'Flagged', desc: 'Significant verification concerns or strong conflicting signals have been detected.' },
  { level: 'UNABLE', color: 'text-zinc-400', bg: 'bg-zinc-400/10 border-zinc-400/20', icon: HelpCircle, label: 'Unable to Verify', desc: 'Verification could not be completed because of factors such as unavailable verification sources, unreadable information, unsupported documents, or connectivity limitations.' },
]

const CONNECTIVITY_MODES = [
  { icon: Wifi, title: 'Connected', desc: 'Full verification workflow through the central server.' },
  { icon: Signal, title: 'Weak Connectivity', desc: 'Essential information can be processed locally while communication is optimized for available connectivity.' },
  { icon: WifiOff, title: 'Offline', desc: 'Verification-related information can be securely queued on the device and synchronized when connectivity is restored.' },
  { icon: RefreshCw, title: 'Frequent Travellers', desc: 'Secure local caching can reduce unnecessary repeated verification for eligible repeat cases while maintaining controlled access and data protection.' },
]

const SECURITY_ITEMS = [
  { icon: Smartphone, title: 'On-Device Preprocessing', desc: 'Initial processing is performed locally wherever practical.' },
  { icon: Lock, title: 'Encrypted Communication', desc: 'Data transmitted between field devices and backend services is protected.' },
  { icon: KeyRound, title: 'Secure Local Storage', desc: 'Offline information and queued verification data are protected on the device.' },
  { icon: UserCog, title: 'Role-Based Access', desc: 'Access to verification information is controlled according to user roles.' },
  { icon: Eye, title: 'Auditability', desc: 'Verification activities and important system actions can be recorded for authorized oversight.' },
  { icon: ShieldCheck, title: 'Tamper-Evident Integrity', desc: 'Where integrity mechanisms are used, their purpose is to strengthen the integrity of records rather than expose sensitive identity information.' },
]

const ADMIN_ITEMS = [
  { icon: BarChart3, title: 'Monitoring', desc: 'View screening activity across authorized operational areas.' },
  { icon: ClipboardList, title: 'Case Management', desc: 'Review cases requiring additional attention.' },
  { icon: FileCheck, title: 'Screening Results', desc: 'Access verification outcomes and supporting reasons.' },
  { icon: FileWarning, title: 'Flagged Cases', desc: 'Track cases requiring officer or administrative review.' },
  { icon: ScrollText, title: 'Audit Logs', desc: 'Maintain a traceable record of important verification activities.' },
  { icon: KeyRound, title: 'Access Control', desc: 'Ensure system information is available only to authorized personnel.' },
]

const FEASIBILITY_ITEMS = [
  { icon: Smartphone, title: 'Mobile-First', desc: 'Designed for officers working across different checkpoint environments.' },
  { icon: Server, title: 'Centralized', desc: 'A common verification platform can support multiple operational locations without requiring a dedicated server at every checkpoint.' },
  { icon: Wifi, title: 'Connectivity-Aware', desc: 'Supports connected, weak-network, and offline operating conditions.' },
  { icon: Lock, title: 'Privacy-Conscious', desc: 'Sensitive information is processed and transmitted with security and data-minimization principles.' },
  { icon: Scale, title: 'Scalable', desc: 'The architecture can be extended to additional checkpoints, document types, and verification sources.' },
]

const FUTURE_SCOPE = [
  { icon: Database, title: 'Authorized Government Data Integration', desc: 'Connect verification workflows with approved government databases and registries.' },
  { icon: Languages, title: 'Expanded Multilingual Support', desc: 'Support additional document types, languages, and scripts.' },
  { icon: Network, title: 'Cross-Checkpoint Intelligence', desc: 'Enable controlled information sharing across participating checkpoints.' },
  { icon: Cctv, title: 'CCTV-Assisted Operations', desc: 'Explore authorized CCTV-based monitoring to support operational oversight.' },
  { icon: Satellite, title: 'Identity & Relationship Analysis', desc: 'Identify patterns and relationships across verification records to assist authorized investigations.' },
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
              Secure &middot; Explainable &middot; Connectivity-Aware
            </div>
            <h1
              className={`mt-8 text-4xl font-semibold leading-[1.1] tracking-tight transition-all delay-100 duration-700 sm:text-5xl lg:text-6xl ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              Intelligent Identity &amp; Document Verification for Border Checkpoints
            </h1>
            <p
              className={`mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground transition-all delay-200 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              PramaanAI assists border and checkpoint personnel in screening identity and travel documents through AI-assisted document analysis, identity verification, tampering detection, and risk-based assessment.
            </p>
            <p
              className={`mt-4 max-w-2xl text-base text-muted-foreground/80 transition-all delay-250 duration-700 ${heroVisible ? 'opacity-100' : 'translate-y-4 opacity-0'}`}
            >
              Designed for real-world field operations &mdash; from connected checkpoints to low-connectivity Border Out Posts.
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
                href="#workflow"
                className="flex items-center gap-2 rounded-lg border border-border px-6 py-3 text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
              >
                View System Workflow
                <ChevronDown className="h-4 w-4" />
              </a>
            </div>
          </div>

          {/* Right — rotating logo */}
          <div
            className={`flex items-center justify-center transition-all delay-400 duration-700 ${heroVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-90'}`}
          >
            <div className="relative">
              <div className="absolute -inset-8 rounded-full bg-accent/5 blur-2xl" />
              <img
                src={logoIcon}
                alt="PramaanAI"
                className="relative h-40 w-40 animate-[spin_20s_linear_infinite] drop-shadow-[0_0_30px_rgba(16,185,129,0.15)] sm:h-52 sm:w-52 lg:h-64 lg:w-64"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section id="problem" className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Securing the First Point of Verification</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              The challenge at the checkpoint
            </h2>
            <p className="mx-auto mt-6 max-w-3xl text-base leading-relaxed text-muted-foreground">
              Border checkpoints handle a continuous flow of people and documents. Manual inspection and basic database lookups can become difficult when officers must identify forged documents, altered information, impersonation, expired documents, or conflicting identity records.
            </p>
            <p className="mx-auto mt-4 max-w-3xl text-base leading-relaxed text-muted-foreground">
              At the same time, verification infrastructure may differ from one checkpoint to another, while network connectivity may be limited.
            </p>
            <p className="mx-auto mt-6 max-w-3xl text-sm font-medium text-foreground/80">
              PramaanAI brings these verification challenges into a single, security-focused workflow.
            </p>
          </RevealSection>
        </div>
      </section>

      {/* Verification Signals */}
      <section id="features" className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">One Platform. Multiple Verification Signals.</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Beyond a single check
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base text-muted-foreground">
              PramaanAI does not rely on a single check. It combines multiple verification signals to provide officers with a clearer picture of a document and identity.
            </p>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {VERIFICATION_SIGNALS.map(({ icon: Icon, title, body }, i) => (
              <RevealSection key={title}>
                <div className="group h-full rounded-xl border border-border bg-card p-6 transition-colors hover:border-accent/30" style={{ animationDelay: `${i * 80}ms` }}>
                  <Icon className="h-7 w-7 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{body}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Workflow */}
      <section id="workflow" className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">From Document Capture to Officer Decision</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              System workflow
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {WORKFLOW_STEPS.map(({ step, title, desc }, i) => (
              <RevealSection key={step}>
                <div className="h-full rounded-xl border border-border bg-card p-6" style={{ animationDelay: `${i * 80}ms` }}>
                  <p className="font-mono text-xs font-bold uppercase tracking-widest text-accent">{step}</p>
                  <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Risk Levels */}
      <section className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Verification Results That Officers Can Understand</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Clear, explainable outcomes
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {RISK_LEVELS.map(({ level, color, bg, icon: Icon, label, desc }) => (
              <RevealSection key={level}>
                <div className={`h-full rounded-xl border p-6 ${bg}`}>
                  <div className="flex items-center gap-3">
                    <Icon className={`h-5 w-5 ${color}`} strokeWidth={2} />
                    <div>
                      <span className={`text-sm font-bold ${color}`}>{level}</span>
                      {label && <span className={`ml-2 text-xs ${color}/70`}>&mdash; {label}</span>}
                    </div>
                  </div>
                  <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
          <RevealSection className="mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              Every result is accompanied by relevant reasons rather than relying on a score alone.
            </p>
          </RevealSection>
        </div>
      </section>

      {/* Connectivity */}
      <section className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Built for Real Checkpoints</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Connectivity cannot always be guaranteed
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {CONNECTIVITY_MODES.map(({ icon: Icon, title, desc }, i) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-border bg-card p-6" style={{ animationDelay: `${i * 80}ms` }}>
                  <Icon className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
          <RevealSection className="mt-8 text-center">
            <p className="text-sm text-muted-foreground">
              The system is designed around field conditions &mdash; not around the assumption of permanent connectivity.
            </p>
          </RevealSection>
        </div>
      </section>

      {/* Security */}
      <section className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Security Begins Before the Server</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Privacy-conscious architecture
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base text-muted-foreground">
              Identity and document information is highly sensitive. PramaanAI follows a privacy-conscious architecture in which unnecessary information exposure is minimized.
            </p>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {SECURITY_ITEMS.map(({ icon: Icon, title, desc }, i) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-border bg-card p-6" style={{ animationDelay: `${i * 80}ms` }}>
                  <Icon className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Multilingual */}
      <section className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Designed for Diverse Documents &amp; Identities</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Multilingual &amp; multiscript verification
            </h2>
            <p className="mx-auto mt-6 max-w-3xl text-base leading-relaxed text-muted-foreground">
              Border verification cannot depend on a single document format or language. PramaanAI is designed to support a multilingual and multiscript verification architecture, enabling document information to be extracted, normalized, and validated across supported document types and scripts.
            </p>
          </RevealSection>
          <RevealSection>
            <div className="mx-auto mt-10 grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
              {['Names & spellings', 'Transliteration', 'Dates & formats', 'Document structures', 'Nationality info', 'Document numbering', 'Travel-document fields', 'Identity fields'].map((item) => (
                <div key={item} className="rounded-lg border border-border bg-card px-4 py-3 text-center text-xs text-muted-foreground">
                  {item}
                </div>
              ))}
            </div>
          </RevealSection>
          <RevealSection className="mt-8 text-center">
            <p className="text-sm text-muted-foreground italic">
              A variation in spelling or transliteration is treated as a verification signal &mdash; not automatically as evidence of fraud.
            </p>
          </RevealSection>
        </div>
      </section>

      {/* Admin Dashboard */}
      <section className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">A Clear View for Command &amp; Administration</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Centralized dashboard
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base text-muted-foreground">
              While officers handle verification at the checkpoint, authorized administrators can monitor activity through a centralized dashboard.
            </p>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {ADMIN_ITEMS.map(({ icon: Icon, title, desc }, i) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-border bg-card p-6" style={{ animationDelay: `${i * 80}ms` }}>
                  <Icon className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Architecture Designed for Field Operations</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              System overview
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Mobile App */}
            <RevealSection>
              <div className="h-full rounded-xl border border-border bg-card p-6">
                <div className="flex items-center gap-3">
                  <MonitorSmartphone className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="text-sm font-semibold text-foreground">Officer Mobile Application</h3>
                </div>
                <div className="mt-5 space-y-2">
                  {['Capture', 'On-Device Processing', 'Local Cache / Offline Queue', 'Secure Synchronization', 'Central Verification'].map((step, i) => (
                    <div key={step} className="flex items-center gap-3">
                      <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10px] font-bold text-accent">{i + 1}</div>
                      <span className="text-xs text-muted-foreground">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            </RevealSection>
            {/* Central Verification */}
            <RevealSection>
              <div className="h-full rounded-xl border border-accent/30 bg-card p-6">
                <div className="flex items-center gap-3">
                  <Server className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="text-sm font-semibold text-foreground">Central Verification</h3>
                </div>
                <div className="mt-5 space-y-2">
                  {['Document Validation', 'OCR & Information Extraction', 'Tampering Analysis', 'Identity Matching', 'Face Verification', 'Multiple Identity Analysis', 'Risk Assessment', 'Explainable Result'].map((step, i) => (
                    <div key={step} className="flex items-center gap-3">
                      <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10px] font-bold text-accent">{i + 1}</div>
                      <span className="text-xs text-muted-foreground">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            </RevealSection>
            {/* Administration */}
            <RevealSection>
              <div className="h-full rounded-xl border border-border bg-card p-6">
                <div className="flex items-center gap-3">
                  <LayoutDashboard className="h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="text-sm font-semibold text-foreground">Administration</h3>
                </div>
                <div className="mt-5 space-y-2">
                  {['Monitoring', 'Case Management', 'Screening Results', 'Flagged Cases', 'Audit & Oversight'].map((step, i) => (
                    <div key={step} className="flex items-center gap-3">
                      <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-accent/10 text-[10px] font-bold text-accent">{i + 1}</div>
                      <span className="text-xs text-muted-foreground">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            </RevealSection>
          </div>
        </div>
      </section>

      {/* User Personas */}
      <section className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Designed for the People Who Use It</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              User-centered design
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-3">
            {[
              { icon: ShieldCheck, title: 'Border & Checkpoint Officers', desc: 'A focused interface for document capture, verification, and clear decision support.' },
              { icon: LayoutDashboard, title: 'Command & Administrative Teams', desc: 'Centralized visibility into screening activity, cases, flagged results, and audit information.' },
              { icon: Globe, title: 'Genuine Travellers', desc: 'A verification process designed to reduce unnecessary repetitive manual checks while keeping the final decision with authorized personnel.' },
            ].map(({ icon: Icon, title, desc }) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-border bg-card p-6 text-center">
                  <Icon className="mx-auto h-8 w-8 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Feasibility */}
      <section className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Feasibility &amp; Operational Value</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Built to be deployable
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {FEASIBILITY_ITEMS.map(({ icon: Icon, title, desc }) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-border bg-card p-5 text-center">
                  <Icon className="mx-auto h-6 w-6 text-accent" strokeWidth={1.5} />
                  <h3 className="mt-3 text-xs font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* Future Scope */}
      <section className="px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <RevealSection className="text-center">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">Future Scope</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
              Roadmap
            </h2>
          </RevealSection>
          <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {FUTURE_SCOPE.map(({ icon: Icon, title, desc }) => (
              <RevealSection key={title}>
                <div className="h-full rounded-xl border border-dashed border-border bg-card/50 p-5 text-center">
                  <Icon className="mx-auto h-6 w-6 text-muted-foreground" strokeWidth={1.5} />
                  <h3 className="mt-3 text-xs font-semibold text-foreground">{title}</h3>
                  <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-secondary/30 px-6 py-24 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <RevealSection>
            <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">PramaanAI</h2>
            <div className="mt-6 space-y-1 text-lg text-muted-foreground">
              <p>Verify identities.</p>
              <p>Understand documents.</p>
              <p>Support better decisions.</p>
            </div>
            <p className="mx-auto mt-6 max-w-xl text-sm text-muted-foreground">
              AI-assisted identity and document verification designed for real-world border and checkpoint operations.
            </p>
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
