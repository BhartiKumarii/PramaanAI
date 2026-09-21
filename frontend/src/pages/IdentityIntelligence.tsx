import { useState, useMemo, useCallback, useEffect } from 'react'
import { Search, Fingerprint, Share2, Calendar, Globe, Eye } from 'lucide-react'
import { searchPersons, listRelationships, expandEntity } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card, StatTile } from '../components/StatTile'
import { NetworkGraphView } from '../components/NetworkGraphView'
import type { PersonSearchResult, NetworkGraph, GraphNode } from '../api/types'

type Tab = 'search' | 'patterns' | 'network'

const TABS: { key: Tab; label: string; icon: typeof Search }[] = [
  { key: 'search', label: 'Person Search', icon: Search },
  { key: 'patterns', label: 'Pattern Analysis', icon: Fingerprint },
  { key: 'network', label: 'Network Graph', icon: Share2 },
]

const RELATIONSHIP_TYPES = [
  { label: 'All types', value: '' },
  { label: 'Same document number', value: 'SAME_DOCUMENT_NUMBER' },
  { label: 'Similar identity (same face)', value: 'SIMILAR_IDENTITY' },
]

const TIME_FILTERS = [
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 },
  { label: 'Last 90 days', value: 90 },
  { label: 'All time', value: 0 },
]

const NATIONALITIES = ['All', 'Indian', 'Nepali', 'Bhutanese', 'Other']

// --- Person Search Tab ---

function PersonSearchTab({ onViewNetwork }: { onViewNetwork: (person: PersonSearchResult) => void }) {
  const [query, setQuery] = useState('')
  const [nationality, setNationality] = useState('All')
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

  const filtered = useMemo(() => {
    if (!results) return null
    if (nationality === 'All') return results
    return results.filter(
      (p) => p.nationality?.toLowerCase() === nationality.toLowerCase(),
    )
  }, [results, nationality])

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="Search by full or partial name..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Globe className="h-3.5 w-3.5 text-muted-foreground" />
              <select
                value={nationality}
                onChange={(e) => setNationality(e.target.value)}
                className="rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground focus:border-ring focus:outline-none"
              >
                {NATIONALITIES.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            {results && (
              <span className="text-xs text-muted-foreground">
                {filtered?.length ?? 0} result{(filtered?.length ?? 0) !== 1 ? 's' : ''} found
              </span>
            )}
          </div>
        </form>
      </Card>

      {error && <p className="text-sm text-status-high">{error}</p>}

      {searched && !loading && filtered && (
        <>
          {filtered.length === 0 && (
            <Card>
              <p className="py-4 text-sm text-muted-foreground">No matches found.</p>
            </Card>
          )}
          {filtered.length > 0 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((p) => (
                <div
                  key={p.id}
                  className="group rounded-xl border border-border bg-card p-4 transition-colors hover:border-accent/50"
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-foreground">{p.full_name}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {p.nationality ?? 'Nationality unknown'}
                      </p>
                    </div>
                    <span className="ml-2 shrink-0 rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                      {p.nationality?.slice(0, 3).toUpperCase() ?? '---'}
                    </span>
                  </div>

                  <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                    <div className="flex justify-between">
                      <span>Document</span>
                      <span className="font-mono text-foreground">
                        {p.masked_document_number ?? 'No doc on file'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>First seen</span>
                      <span className="text-foreground">
                        {new Date(p.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => onViewNetwork(p)}
                      className="flex items-center gap-1.5 rounded-md border border-accent/30 px-2.5 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/10"
                    >
                      <Eye className="h-3 w-3" />
                      View in Network
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!searched && (
        <Card>
          <p className="py-6 text-center text-sm text-muted-foreground">
            Search by name across every declared identity the system has seen. Document numbers
            are never stored in plaintext, so search is by name only.
          </p>
        </Card>
      )}
    </div>
  )
}

// --- Pattern Analysis Tab ---

function PatternAnalysisTab() {
  const [typeFilter, setTypeFilter] = useState('')
  const [timeDays, setTimeDays] = useState(0)
  const relationships = useAsync(
    () => listRelationships(typeFilter ? { relationship_type: typeFilter } : {}),
    [typeFilter],
  )

  const filtered = useMemo(() => {
    if (!relationships.data) return null
    if (timeDays === 0) return relationships.data
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - timeDays)
    return relationships.data.filter((r) => new Date(r.created_at) >= cutoff)
  }, [relationships.data, timeDays])

  const stats = useMemo(() => {
    if (!filtered) return { total: 0, sameDoc: 0, similarFace: 0 }
    return {
      total: filtered.length,
      sameDoc: filtered.filter((r) => r.relationship_type === 'SAME_DOCUMENT_NUMBER').length,
      similarFace: filtered.filter((r) => r.relationship_type === 'SIMILAR_IDENTITY').length,
    }
  }, [filtered])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <StatTile label="Total Patterns" value={stats.total} icon={Fingerprint} delay={0} />
        <StatTile label="Same Document" value={stats.sameDoc} accent="review" delay={80} />
        <StatTile label="Similar Face" value={stats.similarFace} accent="analytical" delay={160} />
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex flex-wrap gap-2">
          {RELATIONSHIP_TYPES.map((t) => (
            <button
              key={t.label}
              onClick={() => setTypeFilter(t.value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                typeFilter === t.value
                  ? 'border-analytical bg-analytical-bg text-analytical'
                  : 'border-border text-muted-foreground hover:bg-card'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
          <div className="flex gap-1">
            {TIME_FILTERS.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTimeDays(tf.value)}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  timeDays === tf.value
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-muted-foreground hover:bg-card'
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        {relationships.loading && <p className="py-6 text-sm text-muted-foreground">Loading...</p>}
        {relationships.error && <p className="text-sm text-status-high">{relationships.error}</p>}
        {filtered && filtered.length === 0 && (
          <Card>
            <p className="py-6 text-sm text-muted-foreground">No relationships recorded yet.</p>
          </Card>
        )}
        {filtered && filtered.length > 0 && (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {filtered.map((rel) => {
              const isSameDoc = rel.relationship_type === 'SAME_DOCUMENT_NUMBER'
              return (
                <div
                  key={rel.id}
                  className={`rounded-xl border p-4 transition-colors ${
                    isSameDoc
                      ? 'border-status-review/30 bg-status-review/5'
                      : 'border-analytical/20 bg-analytical-bg'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          isSameDoc ? 'bg-status-review' : 'bg-analytical'
                        }`}
                      />
                      <span
                        className={`text-xs font-semibold uppercase tracking-wide ${
                          isSameDoc ? 'text-status-review' : 'text-analytical'
                        }`}
                      >
                        {rel.relationship_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(rel.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-foreground">{rel.explanation}</p>
                  {rel.evidence_case_id && (
                    <a
                      href={`/console/cases/${rel.evidence_case_id}`}
                      className="mt-2 inline-block text-xs font-medium text-accent hover:underline"
                    >
                      View evidence case →
                    </a>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// --- Network Graph Tab ---

function NetworkGraphTab({ initialPersonId, initialPersonName }: { initialPersonId: string | null; initialPersonName: string | null }) {
  const [query, setQuery] = useState('')
  const [candidates, setCandidates] = useState<PersonSearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [centerId, setCenterId] = useState<string | null>(initialPersonId)
  const [centerLabel, setCenterLabel] = useState<string | null>(initialPersonName)
  const [graph, setGraph] = useState<NetworkGraph | null>(null)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<GraphNode | null>(null)

  const loadNetwork = useCallback(async (personId: string, personName: string) => {
    setCenterId(personId)
    setCenterLabel(personName)
    setSelected(null)
    setLoadingGraph(true)
    setError(null)
    try {
      setGraph(await expandEntity(personId, 'PERSON'))
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not load network.')
      setGraph(null)
    } finally {
      setLoadingGraph(false)
    }
  }, [])

  useEffect(() => {
    if (initialPersonId && initialPersonName) {
      loadNetwork(initialPersonId, initialPersonName)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
    loadNetwork(person.id, person.full_name)
  }

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              className="w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Search a person by name to center the graph on them..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </form>
        {candidates && candidates.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {candidates.map((c) => (
              <button
                key={c.id}
                onClick={() => selectPerson(c)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  centerId === c.id
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-muted-foreground hover:bg-secondary'
                }`}
              >
                {c.full_name}
              </button>
            ))}
          </div>
        )}
        {candidates && candidates.length === 0 && (
          <p className="mt-3 text-sm text-muted-foreground">No matches.</p>
        )}
      </Card>

      {error && <p className="text-sm text-status-high">{error}</p>}
      {loadingGraph && <p className="text-sm text-muted-foreground">Loading network...</p>}

      {graph && centerId && (
        <Card title={`Network centered on ${centerLabel}`}>
          <NetworkGraphView graph={graph} centerId={centerId} onSelectNode={setSelected} />
          {selected && (
            <div className="mt-3 rounded-md border border-border bg-secondary/50 p-3 text-xs">
              <p className="font-semibold text-foreground">{selected.label}</p>
              <p className="mt-1 text-muted-foreground">{selected.type}</p>
              {selected.detail && Object.keys(selected.detail).length > 0 && (
                <div className="mt-2 space-y-1 border-t border-border pt-2">
                  {Object.entries(selected.detail).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground">{k}</span>
                      <span className="text-foreground">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {!graph && !loadingGraph && !error && (
        <Card>
          <p className="py-8 text-center text-sm text-muted-foreground">
            Pick a declared identity to see connections — same document number or same face
            matched across other cases. Each link is an observation with evidence
            attached, never a conclusion.
          </p>
        </Card>
      )}
    </div>
  )
}

// --- Main Component ---

export function IdentityIntelligence() {
  const [activeTab, setActiveTab] = useState<Tab>('search')
  const [networkPersonId, setNetworkPersonId] = useState<string | null>(null)
  const [networkPersonName, setNetworkPersonName] = useState<string | null>(null)

  function handleViewNetwork(person: PersonSearchResult) {
    setNetworkPersonId(person.id)
    setNetworkPersonName(person.full_name)
    setActiveTab('network')
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Identity Intelligence</h1>
        <p className="text-sm text-muted-foreground">
          Unified identity analysis — search persons, detect patterns across cases and
          checkpoints, and explore relationship networks. Every association is an observation
          with evidence attached, never a conclusion.
        </p>
      </div>

      <div className="flex gap-2">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {activeTab === 'search' && <PersonSearchTab onViewNetwork={handleViewNetwork} />}
      {activeTab === 'patterns' && <PatternAnalysisTab />}
      {activeTab === 'network' && (
        <NetworkGraphTab
          key={networkPersonId ?? 'empty'}
          initialPersonId={networkPersonId}
          initialPersonName={networkPersonName}
        />
      )}
    </div>
  )
}
