import { useState } from 'react'
import { Search } from 'lucide-react'
import { expandEntity, searchPersons } from '../api/resources'
import { NetworkGraphView } from '../components/NetworkGraphView'
import { Card } from '../components/StatTile'
import type { GraphNode, NetworkGraph, PersonSearchResult } from '../api/types'

// Reuses the exact same per-entity graph expansion CaseReview's network
// tab already uses (GET /network/entities/{id}) and the same
// NetworkGraphView renderer — this page just lets an officer pick which
// person to center the graph on, via a name search, instead of arriving
// from a specific case.
export function IdentityNetwork() {
  const [query, setQuery] = useState('')
  const [candidates, setCandidates] = useState<PersonSearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [centerId, setCenterId] = useState<string | null>(null)
  const [centerLabel, setCenterLabel] = useState<string | null>(null)
  const [graph, setGraph] = useState<NetworkGraph | null>(null)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<GraphNode | null>(null)

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setSearching(true)
    setError(null)
    try {
      setCandidates(await searchPersons(query.trim()))
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Search failed.')
    } finally {
      setSearching(false)
    }
  }

  async function selectPerson(person: PersonSearchResult) {
    setCenterId(person.id)
    setCenterLabel(person.full_name)
    setSelected(null)
    setLoadingGraph(true)
    setError(null)
    try {
      setGraph(await expandEntity(person.id, 'PERSON'))
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not load network.')
      setGraph(null)
    } finally {
      setLoadingGraph(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Identity Network</h1>
        <p className="text-sm text-muted-foreground">
          Pick a declared identity to see connections — same document number or same face
          matched across other cases. Each link is an observation with evidence attached, never a
          conclusion.
        </p>
      </div>

      <Card>
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Search a person by name to center the graph on them…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {searching ? 'Searching…' : 'Search'}
          </button>
        </form>
        {candidates && candidates.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {candidates.map((c) => (
              <button
                key={c.id}
                onClick={() => selectPerson(c)}
                className={`rounded-full border px-3 py-1 text-xs font-medium ${
                  centerId === c.id ? 'border-accent bg-accent/10 text-accent' : 'border-border text-muted-foreground hover:bg-secondary'
                }`}
              >
                {c.full_name}
              </button>
            ))}
          </div>
        )}
        {candidates && candidates.length === 0 && <p className="mt-3 text-sm text-muted-foreground">No matches.</p>}
      </Card>

      {error && <p className="text-sm text-status-high">{error}</p>}
      {loadingGraph && <p className="text-sm text-muted-foreground">Loading network…</p>}

      {graph && centerId && (
        <Card title={`Network centered on ${centerLabel}`}>
          <NetworkGraphView graph={graph} centerId={centerId} onSelectNode={setSelected} />
          {selected && (
            <div className="mt-3 rounded-md border border-border bg-secondary/50 p-3 text-xs">
              <p className="font-semibold text-foreground">{selected.label}</p>
              <p className="mt-1 text-muted-foreground">{selected.type}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
