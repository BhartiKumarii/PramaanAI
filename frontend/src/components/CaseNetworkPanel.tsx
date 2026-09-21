import { useEffect, useMemo, useState } from 'react'
import { expandEntity, getCaseNetworkGraph } from '../api/resources'
import type { GraphNode, NetworkGraph } from '../api/types'
import { NetworkGraphView } from './NetworkGraphView'
import { Card } from './StatTile'

function mergeGraphs(a: NetworkGraph, b: NetworkGraph): NetworkGraph {
  const nodeIds = new Set(a.nodes.map((n) => n.id))
  const edgeIds = new Set(a.edges.map((e) => e.id))
  return {
    nodes: [...a.nodes, ...b.nodes.filter((n) => !nodeIds.has(n.id))],
    edges: [...a.edges, ...b.edges.filter((e) => !edgeIds.has(e.id))],
  }
}

export function CaseNetworkPanel({ caseId }: { caseId: string }) {
  const [baseGraph, setBaseGraph] = useState<NetworkGraph | null>(null)
  const [graph, setGraph] = useState<NetworkGraph | null>(null)
  const [centerId, setCenterId] = useState<string | null>(null)
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const [relationshipFilter, setRelationshipFilter] = useState<string>('ALL')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getCaseNetworkGraph(caseId)
      .then((g) => {
        if (cancelled) return
        setBaseGraph(g)
        setGraph(g)
        setCenterId(g.nodes[0]?.id ?? null)
        setSelected(g.nodes[0] ?? null)
      })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail ?? 'Could not load the network graph.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [caseId])

  const relationshipTypes = useMemo(
    () => Array.from(new Set((graph?.edges ?? []).map((e) => e.relationship_type))),
    [graph],
  )

  const filteredGraph = useMemo<NetworkGraph | null>(() => {
    if (!graph) return null
    if (relationshipFilter === 'ALL') return graph
    const edges = graph.edges.filter((e) => e.relationship_type === relationshipFilter)
    const keepIds = new Set<string>([centerId ?? '', ...edges.flatMap((e) => [e.source, e.target])])
    return { nodes: graph.nodes.filter((n) => keepIds.has(n.id)), edges }
  }, [graph, relationshipFilter, centerId])

  async function handleExpand() {
    if (!selected) return
    const expanded = await expandEntity(selected.id, selected.type)
    setGraph((current) => (current ? mergeGraphs(current, expanded) : expanded))
  }

  function handleReset() {
    setGraph(baseGraph)
    setSelected(baseGraph?.nodes[0] ?? null)
    setRelationshipFilter('ALL')
  }

  const relatedEdges = useMemo(
    () => (graph && selected ? graph.edges.filter((e) => e.source === selected.id || e.target === selected.id) : []),
    [graph, selected],
  )

  if (loading) return <Card><p className="text-sm text-muted-foreground">Loading connections…</p></Card>
  if (error) return (
    <Card>
      <div className="py-4 text-center space-y-2">
        <p className="text-2xl">🔗</p>
        <p className="text-sm font-medium text-foreground">No identity connections found</p>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          This traveller has no prior screening records linked in the system.
          Connections are built over multiple screenings — this appears to be a first-time or new entry.
        </p>
      </div>
    </Card>
  )
  if (!filteredGraph || filteredGraph.nodes.length === 0 || !centerId) return (
    <Card>
      <div className="py-4 text-center space-y-2">
        <p className="text-2xl">🔗</p>
        <p className="text-sm font-medium text-foreground">No connections to display</p>
        <p className="text-xs text-muted-foreground">No linked identities, documents, or checkpoints found for this case.</p>
      </div>
    </Card>
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          <select
            value={relationshipFilter}
            onChange={(e) => setRelationshipFilter(e.target.value)}
            className="rounded-md border border-border px-2 py-1 text-xs"
          >
            <option value="ALL">All relationship types</option>
            {relationshipTypes.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleReset}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary"
        >
          Reset Graph
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <NetworkGraphView graph={filteredGraph} centerId={centerId} onSelectNode={setSelected} />
        </div>
        <Card title="Selected Entity">
          {!selected && <p className="text-sm text-muted-foreground">Click a node to see its details.</p>}
          {selected && (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{selected.type}</p>
                <p className="font-medium text-foreground">{selected.label}</p>
              </div>
              {Object.entries(selected.detail ?? {}).length > 0 && (
                <dl className="space-y-1 text-xs text-muted-foreground">
                  {Object.entries(selected.detail).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2">
                      <dt className="text-muted-foreground">{k.replace(/_/g, ' ')}</dt>
                      <dd className="text-right">{v == null ? '—' : String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Related ({relatedEdges.length})
                </p>
                <ul className="space-y-2">
                  {relatedEdges.map((e) => (
                    <li key={e.id} className="rounded-md border border-border bg-secondary p-2 text-xs">
                      <p className="font-medium text-analytical">{e.relationship_type.replace(/_/g, ' ')}</p>
                      <p className="mt-0.5 text-muted-foreground">{e.explanation}</p>
                      <p className="mt-1 text-muted-foreground">{new Date(e.created_at).toLocaleString()}</p>
                    </li>
                  ))}
                  {relatedEdges.length === 0 && <p className="text-xs text-muted-foreground">No relationships recorded.</p>}
                </ul>
              </div>
              <button
                onClick={handleExpand}
                className="w-full rounded-md border border-border py-1.5 text-xs font-medium text-foreground hover:bg-secondary"
              >
                Expand this node
              </button>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
