import { useState } from 'react'
import { listRelationships } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'

const RELATIONSHIP_TYPES = [
  { label: 'All types', value: '' },
  { label: 'Same document number', value: 'SAME_DOCUMENT_NUMBER' },
  { label: 'Similar identity (same face)', value: 'SIMILAR_IDENTITY' },
]

export function IdentityPatterns() {
  const [typeFilter, setTypeFilter] = useState('')
  const relationships = useAsync(
    () => listRelationships(typeFilter ? { relationship_type: typeFilter } : {}),
    [typeFilter],
  )

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Identity &amp; Pattern Analysis</h1>
        <p className="text-sm text-muted-foreground">
          Relevant associations detected across cases and checkpoints — each is an observation with
          evidence attached, never a conclusion. A pattern here is a prompt for authorized human
          review, not proof of anything.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {RELATIONSHIP_TYPES.map((t) => (
          <button
            key={t.label}
            onClick={() => setTypeFilter(t.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              typeFilter === t.value
                ? 'border-analytical bg-analytical-bg text-analytical'
                : 'border-border text-muted-foreground hover:bg-card'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Card>
        {relationships.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {relationships.error && <p className="text-sm text-status-high">{relationships.error}</p>}
        {relationships.data && relationships.data.length === 0 && (
          <p className="py-6 text-sm text-muted-foreground">No relationships recorded yet.</p>
        )}
        {relationships.data && relationships.data.length > 0 && (
          <ul className="space-y-2">
            {relationships.data.map((rel) => (
              <li key={rel.id} className="rounded-md border border-analytical/20 bg-analytical-bg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-analytical">
                    {rel.relationship_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-muted-foreground">{new Date(rel.created_at).toLocaleString()}</span>
                </div>
                <p className="mt-1 text-sm text-foreground">{rel.explanation}</p>
                {rel.evidence_case_id && (
                  <a
                    href={`/console/cases/${rel.evidence_case_id}`}
                    className="mt-1 inline-block text-xs font-medium text-accent hover:underline"
                  >
                    View evidence case →
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
