import { useMemo, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { GraphEdge, GraphNode, NetworkGraph } from '../api/types'

const TYPE_STYLE: Record<string, { badge: string; ring: string; bg: string }> = {
  PERSON: { badge: 'P', ring: 'border-chart-1', bg: 'bg-chart-1' },
  CHECKPOINT: { badge: 'C', ring: 'border-accent', bg: 'bg-accent' },
  VEHICLE: { badge: 'V', ring: 'border-analytical', bg: 'bg-analytical' },
  TRAVEL_EVENT: { badge: 'T', ring: 'border-muted-foreground', bg: 'bg-muted-foreground' },
  DOCUMENT: { badge: 'D', ring: 'border-status-review', bg: 'bg-status-review' },
}

function EntityNode({ data }: NodeProps<{ node: GraphNode; selected: boolean }>) {
  const style = TYPE_STYLE[data.node.type] ?? { badge: '?', ring: 'border-muted-foreground', bg: 'bg-muted-foreground' }
  return (
    <div
      className={`flex items-center gap-2 rounded-full border-2 bg-card px-3 py-1.5 shadow-sm ${
        data.selected ? 'border-accent ring-2 ring-accent/30' : style.ring
      }`}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white ${style.bg}`}>
        {style.badge}
      </span>
      <span className="max-w-[9rem] truncate text-xs font-medium text-foreground">{data.node.label}</span>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  )
}

const NODE_TYPES = { entity: EntityNode }

// No coordinates come from the backend, so lay nodes out ourselves: the
// center entity in the middle, everything it's directly connected to on
// a ring around it, anything further out on a wider ring.
function layout(nodes: GraphNode[], edges: GraphEdge[], centerId: string): Node[] {
  const neighborIds = new Set<string>()
  for (const e of edges) {
    if (e.source === centerId) neighborIds.add(e.target)
    if (e.target === centerId) neighborIds.add(e.source)
  }

  const center = nodes.find((n) => n.id === centerId)
  const inner = nodes.filter((n) => n.id !== centerId && neighborIds.has(n.id))
  const outer = nodes.filter((n) => n.id !== centerId && !neighborIds.has(n.id))

  const result: Node[] = []
  if (center) {
    result.push({ id: center.id, type: 'entity', position: { x: 0, y: 0 }, data: { node: center } })
  }
  const ring = (items: GraphNode[], radius: number) => {
    const count = items.length
    items.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(count, 1)
      result.push({
        id: n.id,
        type: 'entity',
        position: { x: radius * Math.cos(angle), y: radius * Math.sin(angle) },
        data: { node: n },
      })
    })
  }
  ring(inner, 180)
  ring(outer, 340)
  return result
}

export function NetworkGraphView({
  graph,
  centerId,
  onSelectNode,
}: {
  graph: NetworkGraph
  centerId: string
  onSelectNode: (node: GraphNode) => void
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const nodes = useMemo(() => {
    const laidOut = layout(graph.nodes, graph.edges, centerId)
    return laidOut.map((n) => ({ ...n, data: { ...n.data, selected: n.id === selectedId } }))
  }, [graph, centerId, selectedId])

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.relationship_type.replace(/_/g, ' '),
        labelStyle: { fontSize: 10, fill: '#6b7280' },
        style: { stroke: '#7c3aed', strokeWidth: 1.5 },
        animated: false,
      })),
    [graph],
  )

  return (
    <div className="space-y-2">
      <div style={{ height: 360 }} className="rounded-md border border-border bg-card">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onNodeClick={(_, node) => {
            setSelectedId(node.id)
            onSelectNode((node.data as { node: GraphNode }).node)
          }}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} color="#e5e7eb" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {Object.entries(TYPE_STYLE).map(([type, style]) => (
          <span key={type} className="flex items-center gap-1.5">
            <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white ${style.bg}`}>
              {style.badge}
            </span>
            {type.replace('_', ' ')}
          </span>
        ))}
      </div>
    </div>
  )
}
