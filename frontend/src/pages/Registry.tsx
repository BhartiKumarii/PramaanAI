import { useState } from 'react'
import { lookupRegistry, seedMockRegistry } from '../api/resources'
import { Card } from '../components/StatTile'
import type { RegistryLookupResult } from '../api/types'

export function Registry() {
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
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Registry</h1>
        <p className="text-sm text-muted-foreground">
          The mock_central_registry table used during screening — DEMO DATA, not a real government
          database.
        </p>
      </div>

      {error && <p className="text-sm text-status-high">{error}</p>}

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
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input
            className="rounded-md border border-border px-3 py-2 text-sm"
            placeholder="Document number"
            value={docNumber}
            onChange={(e) => setDocNumber(e.target.value)}
          />
          <input
            className="rounded-md border border-border px-3 py-2 text-sm"
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
  )
}
