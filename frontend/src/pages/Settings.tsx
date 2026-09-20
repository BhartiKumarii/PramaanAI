import { useState } from 'react'
import { getRiskConfig, seedMockRegistry, lookupRegistry } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'
import type { RegistryLookupResult } from '../api/types'

export function Settings() {
  const config = useAsync(getRiskConfig, [])

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
    } catch (err) {
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
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Lookup failed.')
    } finally {
      setLooking(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Admin Settings</h1>
        <p className="text-sm text-muted-foreground">
          System configuration, risk engine parameters, and mock registry management.
        </p>
      </div>

      {config.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {config.error && <p className="text-sm text-status-high">{config.error}</p>}

      {config.data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Signal weights">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4">Signal</th>
                  <th className="py-2 pr-4">Weight</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(config.data.weights).map(([signal, weight]) => (
                  <tr key={signal} className="border-b border-border">
                    <td className="py-2 pr-4 font-medium text-foreground">{signal.replace('_', ' ')}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted-foreground">
              A missing signal has its weight dropped and the rest renormalized — never treated as zero
              risk.
            </p>
          </Card>

          <Card title="Risk-level thresholds">
            <div className="flex gap-6 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Low risk ceiling</p>
                <p className="mt-1 font-medium text-status-clear">{config.data.low_risk_ceiling}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Medium risk ceiling</p>
                <p className="mt-1 font-medium text-status-review">{config.data.medium_risk_ceiling}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      <div className="border-t border-border pt-6">
        <h2 className="text-lg font-semibold text-foreground">Mock Registry</h2>
        <p className="text-sm text-muted-foreground">
          The mock_central_registry table used during screening — DEMO DATA, not a real government
          database.
        </p>
      </div>

      {error && <p className="text-sm text-status-high">{error}</p>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Seed synthetic entries">
          <p className="text-xs text-muted-foreground">
            Adds the default set of synthetic watchlist entries used for demo screenings. Safe to run
            repeatedly.
          </p>
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {seeding ? 'Seeding…' : 'Seed default entries'}
          </button>
          {seedResult && <p className="mt-2 text-xs text-status-clear">{seedResult}</p>}
        </Card>

        <Card title="Manual lookup">
          <p className="text-xs text-muted-foreground">
            Runs the same exact/fuzzy lookup the screening pipeline uses.
          </p>
          <div className="mt-3 space-y-3">
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Document number"
              value={docNumber}
              onChange={(e) => setDocNumber(e.target.value)}
            />
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button
              onClick={handleLookup}
              disabled={looking || (!docNumber && !name)}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-60"
            >
              {looking ? 'Looking up…' : 'Look up'}
            </button>
          </div>

          {lookupResult && (
            <div className="mt-4 border-t border-border pt-4">
              <p className={`text-sm font-semibold ${lookupResult.status === 'HIT' ? 'text-status-high' : 'text-status-clear'}`}>
                {lookupResult.status === 'HIT' ? 'Hit found' : 'No hit'}
              </p>
              {lookupResult.hits.map((hit, i) => (
                <div key={i} className="mt-2 rounded-md bg-secondary p-3 text-xs">
                  <p className="font-medium text-foreground">
                    {hit.full_name} — {hit.match_type} match on {hit.matched_field}
                  </p>
                  <p className="mt-1 text-muted-foreground">{hit.explanation}</p>
                  <p className="mt-1 text-muted-foreground">Severity: {hit.severity} · Confidence: {hit.confidence}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
