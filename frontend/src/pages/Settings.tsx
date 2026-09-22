import { useState } from 'react'
import {
  Server,
  Shield,
  Database,
  BookOpen,
  Wifi,
  WifiOff,
  AlertTriangle,
  Trash2,
  Search,
  Sprout,
  Info,
} from 'lucide-react'
import { getRiskConfig, seedMockRegistry, lookupRegistry } from '../api/resources'
import { apiClient, baseURL } from '../api/client'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'
import type { RegistryLookupResult } from '../api/types'

// ── Tabs ──────────────────────────────────────────────────────────────────────

const TABS = [
  { key: 'system', label: 'System', icon: Server },
  { key: 'risk', label: 'Risk Engine', icon: Shield },
  { key: 'data', label: 'Data Management', icon: Database },
  { key: 'registry', label: 'Registry', icon: BookOpen },
] as const

type TabKey = (typeof TABS)[number]['key']

// ── Main ──────────────────────────────────────────────────────────────────────

export function Settings() {
  const [tab, setTab] = useState<TabKey>('system')

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Admin Settings</h1>
        <p className="text-sm text-muted-foreground">
          System configuration, risk engine, data management, and mock registry.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg border border-border bg-secondary/50 p-1">
        {TABS.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                tab === t.key
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'system' && <SystemTab />}
      {tab === 'risk' && <RiskEngineTab />}
      {tab === 'data' && <DataManagementTab />}
      {tab === 'registry' && <RegistryTab />}

      {/* About footer */}
      <div className="border-t border-border pt-5">
        <div className="flex items-start gap-3 rounded-lg border border-border bg-secondary/30 p-4">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="text-xs text-muted-foreground">
            <p className="font-medium text-foreground">PramaanAI v1.0</p>
            <p className="mt-1">
              SIH 2026 &bull; Problem Statement 26188 &bull; Ministry of Home Affairs / Sashastra Seema Bal (SSB)
            </p>
            <p className="mt-1 text-status-review">
              Mock data only — not connected to any real government database. All registry entries are synthetic demo data.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── System Tab ────────────────────────────────────────────────────────────────

function SystemTab() {
  const [healthStatus, setHealthStatus] = useState<'idle' | 'checking' | 'online' | 'error'>('idle')
  const [healthLatency, setHealthLatency] = useState<number | null>(null)
  const [healthError, setHealthError] = useState('')

  async function checkHealth() {
    setHealthStatus('checking')
    setHealthError('')
    const start = Date.now()
    try {
      await apiClient.get('/health', { timeout: 30000 })
      setHealthLatency(Date.now() - start)
      setHealthStatus('online')
    } catch (err: unknown) {
      setHealthLatency(Date.now() - start)
      setHealthStatus('error')
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setHealthError(msg.includes('timeout') ? 'Request timed out — backend may be sleeping (free tier cold start).' : msg)
    }
  }

  return (
    <div className="space-y-5">
      <Card title="Backend Connection">
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">API Endpoint</p>
              <p className="mt-1 rounded-md bg-secondary px-3 py-2 font-mono text-sm text-foreground">
                {baseURL}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Environment</p>
              <p className="mt-1 rounded-md bg-secondary px-3 py-2 text-sm text-foreground">
                {baseURL.startsWith('http') ? 'Production' : 'Development (proxied)'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={checkHealth}
              disabled={healthStatus === 'checking'}
              className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {healthStatus === 'checking' ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
              ) : (
                <Wifi className="h-4 w-4" />
              )}
              {healthStatus === 'checking' ? 'Checking…' : 'Check Backend Health'}
            </button>

            {healthStatus === 'online' && (
              <span className="flex items-center gap-2 text-sm text-status-clear">
                <Wifi className="h-4 w-4" />
                Online — {healthLatency}ms
              </span>
            )}
            {healthStatus === 'error' && (
              <span className="flex items-center gap-2 text-sm text-status-high">
                <WifiOff className="h-4 w-4" />
                Unreachable{healthLatency ? ` (${healthLatency}ms)` : ''}
              </span>
            )}
          </div>
          {healthError && <p className="text-xs text-status-high">{healthError}</p>}
        </div>
      </Card>

      <Card title="Platform Details">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: 'Frontend', value: 'React + Vite' },
            { label: 'Backend', value: 'FastAPI + Python' },
            { label: 'Auth', value: 'JWT + RBAC' },
            { label: 'Database', value: 'PostgreSQL' },
          ].map((item) => (
            <div key={item.label}>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{item.label}</p>
              <p className="mt-1 text-sm font-medium text-foreground">{item.value}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

// ── Risk Engine Tab ───────────────────────────────────────────────────────────

const SIGNAL_LABEL: Record<string, string> = {
  mrz_check: 'MRZ Checksum Verification',
  registry_match: 'Registry Watchlist Match',
  face_match: 'Facial Recognition Match',
  tampering: 'Document Tampering Detection',
  data_consistency: 'Data Cross-Check Consistency',
  ocr_confidence: 'OCR Extraction Confidence',
  expiry_check: 'Document Expiry Validation',
}

function RiskEngineTab() {
  const config = useAsync(getRiskConfig, [])

  if (config.loading) return <p className="text-sm text-muted-foreground">Loading risk configuration…</p>
  if (config.error) return <p className="text-sm text-status-high">{config.error}</p>
  if (!config.data) return null

  const weights = config.data.weights
  const maxWeight = Math.max(...Object.values(weights), 1)

  return (
    <div className="space-y-5">
      <Card title="Signal Weights">
        <p className="mb-4 text-xs text-muted-foreground">
          Each verification signal contributes to the overall risk score. A missing signal has its weight dropped and the rest renormalized — never treated as zero risk.
        </p>
        <div className="space-y-3">
          {Object.entries(weights).map(([signal, weight]) => {
            const pct = Math.round((weight / maxWeight) * 100)
            return (
              <div key={signal}>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-sm font-medium text-foreground">
                    {SIGNAL_LABEL[signal] ?? signal.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs font-semibold text-muted-foreground">{weight}</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-accent transition-all duration-700"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <Card title="Risk-Level Thresholds">
        <p className="mb-4 text-xs text-muted-foreground">
          Score boundaries that determine the risk classification of each screening.
        </p>
        <div className="space-y-4">
          <ThresholdBar
            label="Low Risk"
            range={`0 – ${config.data.low_risk_ceiling}`}
            color="bg-status-clear"
            value={config.data.low_risk_ceiling}
          />
          <ThresholdBar
            label="Medium Risk"
            range={`${config.data.low_risk_ceiling} – ${config.data.medium_risk_ceiling}`}
            color="bg-status-review"
            value={config.data.medium_risk_ceiling - config.data.low_risk_ceiling}
          />
          <ThresholdBar
            label="High Risk"
            range={`${config.data.medium_risk_ceiling} – 100`}
            color="bg-status-high"
            value={100 - config.data.medium_risk_ceiling}
          />
        </div>
      </Card>
    </div>
  )
}

function ThresholdBar({ label, range, color, value }: { label: string; range: string; color: string; value: number }) {
  return (
    <div className="flex items-center gap-4">
      <div className="w-28 shrink-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{range}</p>
      </div>
      <div className="flex-1">
        <div className="h-3 overflow-hidden rounded-full bg-secondary">
          <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${value}%` }} />
        </div>
      </div>
    </div>
  )
}

// ── Data Management Tab ───────────────────────────────────────────────────────

function DataManagementTab() {
  const [confirmText, setConfirmText] = useState('')
  const [resetResult, setResetResult] = useState<Record<string, number | string> | null>(null)
  const [resetting, setResetting] = useState(false)
  const [resetError, setResetError] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)

  async function handleReset() {
    if (confirmText !== 'RESET') return
    setResetting(true)
    setResetError('')
    setResetResult(null)
    try {
      const { data } = await apiClient.delete<{ deleted: Record<string, number | string> }>('/admin/reset-screening')
      setResetResult(data.deleted)
      setShowConfirm(false)
      setConfirmText('')
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string } }; message?: string }
      setResetError(axErr.response?.data?.detail ?? axErr.message ?? 'Reset failed.')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="space-y-5">
      <Card title="Reset Screening Data">
        <div className="flex items-start gap-3 rounded-lg border border-status-high/20 bg-status-high/5 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-status-high" />
          <div>
            <p className="text-sm font-medium text-foreground">Danger Zone</p>
            <p className="mt-1 text-xs text-muted-foreground">
              This permanently deletes all screening cases, verifications, audit events, and related data from the database. This action cannot be undone.
            </p>
          </div>
        </div>

        {!showConfirm ? (
          <button
            onClick={() => setShowConfirm(true)}
            className="mt-4 flex items-center gap-2 rounded-md border border-status-high/40 px-4 py-2 text-sm font-medium text-status-high hover:bg-status-high/10"
          >
            <Trash2 className="h-4 w-4" />
            Reset All Screening Data
          </button>
        ) : (
          <div className="mt-4 space-y-3 rounded-lg border border-border p-4">
            <p className="text-sm text-foreground">
              Type <span className="font-mono font-bold text-status-high">RESET</span> to confirm:
            </p>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Type RESET"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleReset}
                disabled={confirmText !== 'RESET' || resetting}
                className="flex items-center gap-2 rounded-md bg-status-high px-4 py-2 text-sm font-semibold text-white hover:bg-status-high/90 disabled:opacity-40"
              >
                {resetting && <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                {resetting ? 'Resetting…' : 'Confirm Reset'}
              </button>
              <button
                onClick={() => { setShowConfirm(false); setConfirmText('') }}
                className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {resetError && <p className="mt-3 text-sm text-status-high">{resetError}</p>}

        {resetResult && (
          <div className="mt-4 rounded-lg border border-status-clear/20 bg-status-clear/5 p-4">
            <p className="mb-2 text-sm font-medium text-status-clear">Data cleared successfully</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(resetResult).map(([table, count]) => (
                <div key={table} className="rounded-md bg-secondary px-3 py-2">
                  <p className="text-xs text-muted-foreground">{table.replace(/_/g, ' ')}</p>
                  <p className="text-sm font-semibold text-foreground">{count === 'skipped' ? '—' : count}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card title="Data Retention">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            { label: 'Screening Records', note: 'All case data, verifications, and decisions' },
            { label: 'Audit Events', note: 'Timestamped log of all system actions' },
            { label: 'Uploaded Images', note: 'Document and selfie images stored on server' },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-border p-3">
              <p className="text-sm font-medium text-foreground">{item.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{item.note}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

// ── Registry Tab ──────────────────────────────────────────────────────────────

function RegistryTab() {
  const [seedResult, setSeedResult] = useState<string | null>(null)
  const [seeding, setSeeding] = useState(false)
  const [docNumber, setDocNumber] = useState('')
  const [name, setName] = useState('')
  const [lookupResult, setLookupResult] = useState<RegistryLookupResult | null>(null)
  const [looking, setLooking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSeed() {
    setSeeding(true)
    setError(null)
    try {
      const res = await seedMockRegistry()
      setSeedResult(`Seeded ${res.seeded} synthetic entries.`)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not seed registry.')
    } finally {
      setSeeding(false)
    }
  }

  async function handleLookup() {
    setLooking(true)
    setError(null)
    setLookupResult(null)
    try {
      const res = await lookupRegistry({ document_number: docNumber || undefined, name: name || undefined })
      setLookupResult(res)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Lookup failed.')
    } finally {
      setLooking(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-lg border border-status-review/20 bg-status-review/5 p-4">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-status-review" />
        <p className="text-xs text-muted-foreground">
          The mock_central_registry table contains <strong className="text-foreground">synthetic demo data only</strong> — not connected to any real government database. All entries are fabricated for demonstration purposes.
        </p>
      </div>

      {error && <p className="text-sm text-status-high">{error}</p>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card title="Seed Synthetic Entries">
          <p className="text-xs text-muted-foreground">
            Populates the mock registry with default synthetic watchlist entries for demo screenings. Safe to run repeatedly — duplicates are skipped.
          </p>
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="mt-4 flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            <Sprout className="h-4 w-4" />
            {seeding ? 'Seeding…' : 'Seed Default Entries'}
          </button>
          {seedResult && (
            <p className="mt-3 flex items-center gap-2 text-xs text-status-clear">
              <span className="h-1.5 w-1.5 rounded-full bg-status-clear" />
              {seedResult}
            </p>
          )}
        </Card>

        <Card title="Manual Registry Lookup">
          <p className="text-xs text-muted-foreground">
            Runs the same exact/fuzzy lookup the screening pipeline uses against the mock registry.
          </p>
          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Document Number</label>
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="e.g. A1234567"
                value={docNumber}
                onChange={(e) => setDocNumber(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Full Name</label>
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="e.g. Rajesh Kumar"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <button
              onClick={handleLookup}
              disabled={looking || (!docNumber && !name)}
              className="flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-60"
            >
              <Search className="h-4 w-4" />
              {looking ? 'Looking up…' : 'Look Up'}
            </button>
          </div>

          {lookupResult && (
            <div className="mt-4 border-t border-border pt-4">
              <p
                className={`flex items-center gap-2 text-sm font-semibold ${
                  lookupResult.status === 'HIT' ? 'text-status-high' : 'text-status-clear'
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${lookupResult.status === 'HIT' ? 'bg-status-high' : 'bg-status-clear'}`}
                />
                {lookupResult.status === 'HIT' ? `${lookupResult.hits.length} hit(s) found` : 'No match found'}
              </p>
              {lookupResult.hits.map((hit, i) => (
                <div key={i} className="mt-3 rounded-lg border border-border bg-secondary/50 p-3">
                  <p className="text-sm font-medium text-foreground">
                    {hit.full_name}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {hit.match_type} match on <span className="font-medium text-foreground">{hit.matched_field}</span>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{hit.explanation}</p>
                  <div className="mt-2 flex gap-4 text-xs">
                    <span className="text-muted-foreground">
                      Severity: <span className="font-medium text-foreground">{hit.severity}</span>
                    </span>
                    <span className="text-muted-foreground">
                      Confidence: <span className="font-medium text-foreground">{hit.confidence}</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
