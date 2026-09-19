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
  // Person nodes with face match status differentiation
  PERSON_NEW: { badge: 'N', ring: 'border-emerald-500', bg: 'bg-emerald-500' },        // New face - green
  PERSON_VERIFIED: { badge: 'V', ring: 'border-blue-500', bg: 'bg-blue-500' },        // Verified match - blue
  PERSON_PARTIAL: { badge: 'P', ring: 'border-amber-500', bg: 'bg-amber-500' },       // Partial match - amber
  PERSON_UNKNOWN: { badge: '?', ring: 'border-gray-500', bg: 'bg-gray-500' },         // Unknown - gray

  // Fallback for legacy PERSON type
  PERSON: { badge: 'P', ring: 'border-chart-1', bg: 'bg-chart-1' },

  // Other entity types
  CHECKPOINT: { badge: 'C', ring: 'border-accent', bg: 'bg-accent' },
  VEHICLE: { badge: 'V', ring: 'border-analytical', bg: 'bg-analytical' },
  TRAVEL_EVENT: { badge: 'T', ring: 'border-muted-foreground', bg: 'bg-muted-foreground' },
  DOCUMENT: { badge: 'D', ring: 'border-status-review', bg: 'bg-status-review' },
}

// Helper to determine person node type from face match status
function getPersonNodeType(node: GraphNode): string {
  if (node.type !== 'PERSON') return node.type

  const faceMatchStatus = node.detail?.faceMatchStatus as string | undefined
  const faceConfidence = (node.detail?.faceConfidence as number) || 0

  switch (faceMatchStatus) {
    case 'NEW_FACE': return 'PERSON_NEW'
    case 'VERIFIED_MATCH': return 'PERSON_VERIFIED'
    case 'PARTIAL_MATCH': return 'PERSON_PARTIAL'
    case 'NO_FACE_DATA':
    case 'UNKNOWN':
    default:
      // Use confidence as fallback if status not available
      if (faceConfidence >= 0.8) return 'PERSON_VERIFIED'
      if (faceConfidence >= 0.5) return 'PERSON_PARTIAL'
      return 'PERSON_UNKNOWN'
  }
}

function EntityNode({ data }: NodeProps<{ node: GraphNode; selected: boolean }>) {
  const nodeType = getPersonNodeType(data.node)
  const style = TYPE_STYLE[nodeType] ?? { badge: '?', ring: 'border-muted-foreground', bg: 'bg-muted-foreground' }

  const faceConfidence = (data.node.detail?.faceConfidence as number) || 0
  const previousEncounters = (data.node.detail?.previousEncounters as number) || 0
  const isPersonNode = data.node.type === 'PERSON'

  return (
    <div className="relative">
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />

      <div
        className={`flex items-center gap-2 rounded-full border-2 bg-card px-3 py-1.5 shadow-sm ${
          data.selected ? 'border-accent ring-2 ring-accent/30' : style.ring
        }`}
      >
        {/* Face confidence ring for person nodes */}
        {isPersonNode && faceConfidence > 0 && (
          <div
            className={`absolute -inset-1 rounded-full border-2 ${
              faceConfidence >= 0.8 ? 'border-emerald-400' :
              faceConfidence >= 0.6 ? 'border-amber-400' :
              'border-red-400'
            }`}
            style={{ opacity: 0.3 + (faceConfidence * 0.5) }}
          />
        )}

        <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white ${style.bg}`}>
          {style.badge}
        </span>

        <span className="max-w-[9rem] truncate text-xs font-medium text-foreground">
          {data.node.label}
        </span>

        {/* Previous encounters badge for person nodes */}
        {isPersonNode && previousEncounters > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-[8px] font-bold text-white">
            {previousEncounters > 9 ? '9+' : previousEncounters}
          </span>
        )}
      </div>

      {/* Face confidence percentage display */}
      {isPersonNode && faceConfidence > 0 && data.selected && (
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded bg-black/75 px-1 py-0.5 text-[10px] text-white">
          {Math.round(faceConfidence * 100)}%
        </div>
      )}

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
      graph.edges.map((e) => {
        // Enhanced edge styling based on relationship type
        const getEdgeStyle = (relationshipType: string) => {
          switch (relationshipType) {
            case 'FACE_VERIFIED':
              return { stroke: '#10b981', strokeWidth: 3, strokeDasharray: 'none' }     // Solid thick green
            case 'FACE_SIMILAR':
              return { stroke: '#3b82f6', strokeWidth: 2, strokeDasharray: '8,4' }      // Dashed blue
            case 'DOCUMENT_LINKED':
              return { stroke: '#8b5cf6', strokeWidth: 2, strokeDasharray: '4,4' }      // Dotted purple
            case 'TRAVEL_HISTORY':
              return { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '12,6' }   // Long dash orange
            case 'IDENTITY_MATCH':
            default:
              return { stroke: '#6b7280', strokeWidth: 1.5, strokeDasharray: 'none' }   // Regular gray
          }
        }

        const style = getEdgeStyle(e.relationship_type)
        const labelText = e.relationship_type.replace(/_/g, ' ')

        return {
          id: e.id,
          source: e.source,
          target: e.target,
          label: labelText,
          labelStyle: {
            fontSize: 10,
            fill: style.stroke,
            fontWeight: 'bold',
            backgroundColor: 'rgba(255, 255, 255, 0.8)',
            padding: '2px 4px',
            borderRadius: '4px',
          },
          style: {
            stroke: style.stroke,
            strokeWidth: style.strokeWidth,
            strokeDasharray: style.strokeDasharray,
          },
          animated: e.relationship_type === 'FACE_VERIFIED', // Animate verified face matches
        }
      }),
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
      {/* Enhanced Legend */}
      <div className="space-y-3">
        {/* Node Types Legend */}
        <div>
          <h4 className="text-sm font-medium text-foreground mb-2">Node Types</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-muted-foreground">
            {/* Person nodes with face match status */}
            <span className="flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white bg-emerald-500">N</span>
              New Face
            </span>
            <span className="flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white bg-blue-500">V</span>
              Verified Match
            </span>
            <span className="flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white bg-amber-500">P</span>
              Partial Match
            </span>
            <span className="flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white bg-gray-500">?</span>
              Unknown
            </span>

            {/* Other entity types */}
            {Object.entries(TYPE_STYLE)
              .filter(([type]) => !type.startsWith('PERSON'))
              .map(([type, style]) => (
                <span key={type} className="flex items-center gap-1.5">
                  <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white ${style.bg}`}>
                    {style.badge}
                  </span>
                  {type.replace('_', ' ')}
                </span>
              ))}
          </div>
        </div>

        {/* Connection Types Legend */}
        <div>
          <h4 className="text-sm font-medium text-foreground mb-2">Connection Types</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 bg-emerald-500"></div>
              Face Verified
            </span>
            <span className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 bg-blue-500 border-dashed" style={{ borderTop: '2px dashed #3b82f6', height: 0 }}></div>
              Face Similar
            </span>
            <span className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 bg-purple-500" style={{ backgroundImage: 'repeating-linear-gradient(to right, #8b5cf6, #8b5cf6 2px, transparent 2px, transparent 6px)' }}></div>
              Document Linked
            </span>
            <span className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 bg-amber-500" style={{ backgroundImage: 'repeating-linear-gradient(to right, #f59e0b, #f59e0b 8px, transparent 8px, transparent 12px)' }}></div>
              Travel History
            </span>
            <span className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 bg-gray-500"></div>
              Identity Match
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
