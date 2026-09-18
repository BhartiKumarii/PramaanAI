import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  addCaseNote,
  decideCase,
  getCase,
  getCaseIdentityHistory,
  getCaseTimeline,
  submitCase,
} from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'
import { StatusBadge, PriorityBadge } from '../components/StatusBadge'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { CaseNetworkPanel } from '../components/CaseNetworkPanel'
import type { DecisionValue } from '../api/types'

type Tab = 'evidence' | 'identity' | 'network' | 'timeline'

function SignalRow({
  label,
  status,
  tone,
  explanation,
}: {
  label: string
  status: string
  tone: 'clear' | 'review' | 'high' | 'neutral'
  explanation: string
}) {
  const toneClass = {
    clear: 'text-status-clear',
    review: 'text-status-review',
    high: 'text-status-high',
    neutral: 'text-muted-foreground',
  }[tone]

  return (
    <div className="border-b border-border py-3 last:border-0">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className={`text-xs font-semibold uppercase tracking-wide ${toneClass}`}>{status}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{explanation}</p>
    </div>
  )
}

export function CaseReview() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('evidence')
  const [confirmDecision, setConfirmDecision] = useState<DecisionValue | null>(null)
  const [noteText, setNoteText] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const caseQuery = useAsync(() => getCase(caseId!), [caseId])
  const identityHistory = useAsync(() => getCaseIdentityHistory(caseId!), [caseId])
  const timeline = useAsync(() => getCaseTimeline(caseId!), [caseId])

  async function handleDecision(decision: DecisionValue, reason: string) {
    if (decision !== 'CLEAR' && !reason.trim()) {
      setActionError('A reason is required for Secondary Review and Hold/Refer.')
      return
    }
    try {
      await decideCase(caseId!, decision, reason || undefined)
      setConfirmDecision(null)
      setActionError(null)
      caseQuery.refetch()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setActionError(detail ?? 'Could not record decision.')
    }
  }

  async function handleAddNote() {
    if (!noteText.trim()) return
    await addCaseNote(caseId!, noteText)
    setNoteText('')
    caseQuery.refetch()
  }

  if (caseQuery.loading) return <p className="text-sm text-muted-foreground">Loading case…</p>
  if (caseQuery.error) return <p className="text-sm text-status-high">{caseQuery.error}</p>
  const c = caseQuery.data
  if (!c) return null

  const v = c.verification

  return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="text-xs text-accent hover:underline">
        ← Back
      </button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{c.case_number}</h1>
          <p className="text-sm text-muted-foreground">
            {c.traveler_name ?? 'Name not extracted'} · {c.document_type} · {c.nationality}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Checkpoint {c.checkpoint_code} · Scanned by {c.field_officer_username} ·{' '}
            {new Date(c.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          <StatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="flex gap-1 border-b border-border">
            {(
              [
                ['evidence', 'Evidence'],
                ['identity', 'Identity History'],
                ['network', 'Network Analysis'],
                ['timeline', 'Timeline'],
              ] as [Tab, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-3 py-2 text-sm font-medium ${
                  tab === key ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === 'evidence' && (
            <Card>
              <p className="mb-3 rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground">
                Document images are not retained after processing — only the derived signals below are
                stored, per data-minimization policy.
              </p>
              {!v && <p className="text-sm text-muted-foreground">No verification evidence attached to this case.</p>}
              {v && (
                <>
                  {v.ocr && (
                    <SignalRow
                      label="OCR Extraction"
                      status={`${Math.round(v.ocr.ocr_confidence * 100)}% confidence`}
                      tone="neutral"
                      explanation={Object.entries(v.ocr.fields)
                        .map(([k, val]) => `${k}: ${val}`)
                        .join(' · ')}
                    />
                  )}
                  {v.validation && (
                    <SignalRow
                      label="Document Validation (MRZ / Verhoeff)"
                      status={v.validation.status}
                      tone={v.validation.status === 'PASS' ? 'clear' : 'high'}
                      explanation={v.validation.findings.map((f) => f.reason).join(' · ') || 'No findings.'}
                    />
                  )}
                  {v.tampering && (
                    <SignalRow
                      label="Document Forensics (ELA)"
                      status={`${Math.round(v.tampering.tampering_risk * 100)}% anomaly risk`}
                      tone={v.tampering.tampering_risk > 0.5 ? 'high' : v.tampering.tampering_risk > 0.25 ? 'review' : 'clear'}
                      explanation={v.tampering.findings[0]?.reason ?? 'No anomalies above baseline.'}
                    />
                  )}
                  {v.deepfake && (
                    <SignalRow
                      label="Deepfake Heuristic"
                      status={v.deepfake.status}
                      tone={v.deepfake.status !== 'ANALYZED' ? 'neutral' : (v.deepfake.score ?? 0) > 0.5 ? 'high' : 'clear'}
                      explanation={v.deepfake.reason}
                    />
                  )}
                  {v.face && (
                    <SignalRow
                      label="Face Match"
                      status={v.face.match ? 'MATCH' : 'NO MATCH'}
                      tone={v.face.match ? 'clear' : 'high'}
                      explanation={v.face.reason}
                    />
                  )}
                  {v.liveness && (
                    <SignalRow
                      label="Liveness Check"
                      status={v.liveness.status}
                      tone={v.liveness.status === 'LIVE' ? 'clear' : v.liveness.status === 'SUSPECTED_SPOOF' ? 'high' : 'neutral'}
                      explanation={v.liveness.reason}
                    />
                  )}
                  {v.identity_graph && (
                    <SignalRow
                      label="Identity Graph"
                      status={v.identity_graph.status.replace('_', ' ')}
                      tone={v.identity_graph.status === 'CLUSTER_FOUND' ? 'review' : 'clear'}
                      explanation={v.identity_graph.reason}
                    />
                  )}
                  {v.registry && (
                    <SignalRow
                      label="Registry Lookup (mock_central_registry)"
                      status={v.registry.status}
                      tone={v.registry.status === 'HIT' ? 'high' : 'clear'}
                      explanation={
                        v.registry.hits.map((h) => `${h.match_type}: ${h.explanation}`).join(' · ') || 'No hits.'
                      }
                    />
                  )}
                </>
              )}
            </Card>
          )}

          {tab === 'identity' && (
            <Card>
              {identityHistory.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {identityHistory.data && identityHistory.data.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No other case's live capture matched this face — either no cluster was found, or no live
                  capture was taken during this screening.
                </p>
              )}
              {identityHistory.data && identityHistory.data.length > 0 && (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-4">Case</th>
                      <th className="py-2 pr-4">Declared Name</th>
                      <th className="py-2 pr-4">Document</th>
                      <th className="py-2 pr-4">Checkpoint</th>
                      <th className="py-2 pr-4">Similarity</th>
                      <th className="py-2 pr-4">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {identityHistory.data.map((r) => (
                      <tr key={r.record_id} className="border-b border-border">
                        <td className="py-2 pr-4 font-medium text-foreground">{r.case_number ?? '—'}</td>
                        <td className="py-2 pr-4">{r.declared_name}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{r.masked_document_number ?? '—'}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{r.checkpoint_code ?? '—'}</td>
                        <td className="py-2 pr-4">
                          {r.similarity != null ? `${Math.round(r.similarity * 100)}%` : 'not directly compared'}
                        </td>
                        <td className="py-2 pr-4 text-muted-foreground">{r.review_status ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          )}

          {tab === 'network' && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                A relationship shown here is an observation the system recorded, not an accusation — click any
                node for details, or expand it to pull in what it's connected to beyond this case.
              </p>
              <CaseNetworkPanel caseId={c.id} />
            </div>
          )}

          {tab === 'timeline' && (
            <Card>
              {timeline.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {timeline.data && (
                <ol className="space-y-3 border-l-2 border-border pl-4">
                  {timeline.data.map((event, i) => (
                    <li key={i}>
                      <p className="text-xs text-muted-foreground">{new Date(event.created_at).toLocaleString()}</p>
                      <p className="text-sm font-medium text-foreground">{event.action}</p>
                      {event.actor_username && <p className="text-xs text-muted-foreground">by {event.actor_username}</p>}
                      {event.detail && <p className="text-xs text-muted-foreground">"{event.detail}"</p>}
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          )}
        </div>

        <div className="space-y-4">
          {v && (
            <Card title="Risk Assessment">
              <p className="text-2xl font-semibold text-foreground">{v.risk.score}/100</p>
              <p
                className={`text-xs font-semibold uppercase tracking-wide ${
                  v.risk.level === 'HIGH_RISK'
                    ? 'text-status-high'
                    : v.risk.level === 'MEDIUM_RISK'
                      ? 'text-status-review'
                      : 'text-status-clear'
                }`}
              >
                {v.risk.level.replace('_', ' ')}
              </p>
              <p className="mt-3 text-sm text-muted-foreground">{v.risk.top_reason}</p>
              <ul className="mt-3 space-y-1.5 border-t border-border pt-3 text-xs text-muted-foreground">
                {v.risk.breakdown.map((b) => (
                  <li key={b.signal}>
                    <span className="font-medium text-foreground">{b.signal}:</span> {b.reason}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {(c.status === 'SENT' || c.status === 'REVIEW_REQUIRED') && (
            <Card title="Decision">
              {actionError && <p className="mb-2 text-xs text-status-high">{actionError}</p>}
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => setConfirmDecision('CLEAR')}
                  className="rounded-md bg-status-clear px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
                >
                  Clear
                </button>
                <button
                  onClick={() => setConfirmDecision('SECONDARY_REVIEW')}
                  className="rounded-md bg-status-review px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
                >
                  Secondary Review
                </button>
                <button
                  onClick={() => setConfirmDecision('HOLD_REFER')}
                  className="rounded-md bg-status-high px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
                >
                  Hold / Refer
                </button>
              </div>
            </Card>
          )}

          {c.status === 'PENDING' && (
            <Card title="Forward Case">
              <p className="mb-2 text-xs text-muted-foreground">Send this case to the Immigration Officer queue.</p>
              <button
                onClick={async () => {
                  await submitCase(c.id)
                  caseQuery.refetch()
                }}
                className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                Send to Immigration
              </button>
            </Card>
          )}

          {c.decisions.length > 0 && (
            <Card title="Decision History">
              <ul className="space-y-2 text-sm">
                {c.decisions.map((d, i) => (
                  <li key={i} className="border-b border-border pb-2 last:border-0">
                    <p className="font-medium text-foreground">{d.decision.replace('_', ' ')}</p>
                    <p className="text-xs text-muted-foreground">
                      {d.officer_username} · {new Date(d.created_at).toLocaleString()}
                    </p>
                    {d.reason && <p className="mt-1 text-xs text-muted-foreground">"{d.reason}"</p>}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title="Notes">
            <ul className="mb-3 space-y-2 text-sm">
              {c.notes.map((n) => (
                <li key={n.id} className="border-b border-border pb-2 last:border-0">
                  <p className="text-xs text-muted-foreground">
                    {n.author_username} · {new Date(n.created_at).toLocaleString()}
                  </p>
                  <p className="whitespace-pre-line">{n.note}</p>
                </li>
              ))}
              {c.notes.length === 0 && <p className="text-sm text-muted-foreground">No notes yet.</p>}
            </ul>
            <textarea
              className="w-full rounded-md border border-border p-2 text-sm focus:border-ring focus:outline-none"
              rows={2}
              placeholder="Add a note…"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
            />
            <button
              onClick={handleAddNote}
              className="mt-2 w-full rounded-md border border-border py-1.5 text-sm font-medium text-foreground hover:bg-secondary"
            >
              Add Note
            </button>
          </Card>
        </div>
      </div>

      {confirmDecision && (
        <ConfirmDialog
          title={`Confirm: ${confirmDecision.replace('_', ' ')}`}
          description="This is the authorised final decision on this case and will be permanently logged."
          confirmLabel="Confirm Decision"
          requireReason={confirmDecision !== 'CLEAR'}
          onCancel={() => setConfirmDecision(null)}
          onConfirm={(reason) => handleDecision(confirmDecision, reason)}
        />
      )}
    </div>
  )
}
