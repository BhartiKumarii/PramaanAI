import { useState } from 'react'
import { Search } from 'lucide-react'
import { searchPersons } from '../api/resources'
import { Card } from '../components/StatTile'
import type { PersonSearchResult } from '../api/types'

export function PersonSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PersonSearchResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const data = await searchPersons(query.trim())
      setResults(data)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Search failed.')
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Person Search</h1>
        <p className="text-sm text-muted-foreground">
          Name search across every declared identity the system has seen. Document numbers are never
          stored in plaintext, so search is by name only — use Registry lookup for a document-number
          check.
        </p>
      </div>

      <Card>
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Full or partial name…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </Card>

      {error && <p className="text-sm text-status-high">{error}</p>}

      {searched && !loading && results && (
        <Card>
          {results.length === 0 && <p className="py-4 text-sm text-muted-foreground">No matches.</p>}
          {results.length > 0 && (
            <ul className="divide-y divide-border">
              {results.map((p) => (
                <li key={p.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">{p.full_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {p.nationality ?? 'Nationality unknown'} · {p.masked_document_number ?? 'No document number on file'}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">{new Date(p.created_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  )
}
