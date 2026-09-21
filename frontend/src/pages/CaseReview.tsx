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
import { useAuth } from '../auth/AuthContext'
import { Card } from '../components/StatTile'
import { StatusBadge, PriorityBadge } from '../components/StatusBadge'
import { CaseNetworkPanel } from '../components/CaseNetworkPanel'
import { EvidenceImages } from '../components/EvidenceImages'
import type { DecisionValue, VerificationRecordResponse } from '../api/types'

type Tab = 'evidence' | 'identity' | 'network' | 'timeline'

// ── Human-readable finding translation ──────────────────────────────────────

type FindingTone = 'clear' | 'review' | 'alert' | 'none'

interface FindingCard {
  label: string
  tone: FindingTone
  summary: string
  detail?: string
}

const SIGNAL_LABELS: Record<string, string> = {
  checksum: 'Document Checks',
  forensics: 'Document Appearance',
  face_match: 'Photo Match',
  face_detection: 'Photo Quality',
  deepfake: 'Photo Authenticity',
  liveness: 'Live Person Check',
  blacklist: 'Security Records',
  identity_graph: 'Identity Records',
  duplicate_document: 'Document History',
  citizen_registry: 'Registry Check',
}

function signalToFinding(signal: string, rawRisk: number, reason: string): FindingCard {
  const label = SIGNAL_LABELS[signal] ?? signal.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  const tone: FindingTone = rawRisk >= 0.5 ? 'alert' : rawRisk >= 0.1 ? 'review' : 'clear'

  const summaries: Record<string, { clear: string; review: string; alert: string }> = {
    checksum: {
      clear: 'Document format and data checks passed.',
      review: 'Some document format checks need review.',
      alert: 'Document format checks failed — possible invalid or altered document.',
    },
    forensics: {
      clear: 'No obvious signs of alteration detected.',
      review: 'Document appearance requires additional review.',
      alert: 'Possible image alteration or editing detected.',
    },
    face_match: {
      clear: 'Live photo matches the document photo.',
      review: 'Partial match — photo comparison needs review.',
      alert: 'Live photo does not match the document photo.',
    },
    face_detection: {
      clear: 'Face clearly detected in the live photo.',
      review: 'Face detection uncertain — photo may need retaking.',
      alert: 'No face detected in the live photo. Retake required.',
    },
    deepfake: {
      clear: 'Photo appears authentic.',
      review: 'Photo authenticity uncertain — requires review.',
      alert: 'Photo authenticity concern — may require re-capture.',
    },
    liveness: {
      clear: 'Live person confirmed.',
      review: 'Live person check uncertain.',
      alert: 'Photo appears to be from a screen or printed image — retake required.',
    },
    blacklist: {
      clear: 'No matching security record found.',
      review: 'A partial security record match was found.',
      alert: 'Security record match found — requires immediate review.',
    },
    identity_graph: {
      clear: 'No conflicting identity records found.',
      review: 'Similar identity records found — further review recommended.',
      alert: 'Possible duplicate identity detected across multiple records.',
    },
    duplicate_document: {
      clear: 'Document number check completed — no prior record.',
      review: 'Document number appeared previously — review recommended.',
      alert: 'Document number already used in another case.',
    },
    citizen_registry: {
      clear: 'Registry check completed — details match.',
      review: 'Registry record found with partial match.',
      alert: 'Registry mismatch detected — details do not match records.',
    },
  }

  const s = summaries[signal]
  const summary = s ? s[tone] : tone === 'clear' ? 'Check passed.' : tone === 'review' ? 'Requires review.' : 'Issue detected.'

  return { label, tone, summary, detail: reason }
}

function buildFindings(v: VerificationRecordResponse): FindingCard[] {
  const findings: FindingCard[] = []
  for (const b of v.risk.breakdown) {
    if (b.raw_risk > 0 || b.signal === 'blacklist' || b.signal === 'duplicate_document' || b.signal === 'citizen_registry') {
      findings.push(signalToFinding(b.signal, b.raw_risk, b.reason))
    }
  }
  // Always show blacklist + duplicate even if 0 contribution
  const presentSignals = new Set(findings.map((f) => f.label))
  if (!presentSignals.has(SIGNAL_LABELS.blacklist) && v.registry) {
    findings.push(signalToFinding('blacklist', v.registry.status === 'HIT' ? 0.9 : 0, v.registry.status === 'HIT' ? 'Security alert found.' : 'No matching security record found.'))
  }
  if (!presentSignals.has(SIGNAL_LABELS.duplicate_document) && v.duplicate_document) {
    const isDuplicate = v.duplicate_document.status !== 'NO_MATCH'
    findings.push(signalToFinding('duplicate_document', isDuplicate ? 0.8 : 0, v.duplicate_document.reason))
  }
  return findings
}

// ── Finding card component ───────────────────────────────────────────────────

function FindingRow({ f }: { f: FindingCard }) {
  const [expanded, setExpanded] = useState(false)
  const toneStyles: Record<FindingTone, { icon: string; text: string; bg: string }> = {
    clear: { icon: '✓', text: 'text-status-clear', bg: 'bg-status-clear-bg' },
    review: { icon: '⚠', text: 'text-status-review', bg: 'bg-status-review-bg' },
    alert: { icon: '✕', text: 'text-status-high', bg: 'bg-status-high-bg' },
    none: { icon: '–', text: 'text-muted-foreground', bg: 'bg-secondary' },
  }
  const s = toneStyles[f.tone]
  return (
    <div className="border-b border-border last:border-0">
      <button
        className="flex w-full items-start gap-3 py-3 text-left"
        onClick={() => f.detail && setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${s.bg} ${s.text}`}>
          {s.icon}
        </span>
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">{f.label}</p>
          <p className="text-xs text-muted-foreground">{f.summary}</p>
        </div>
        {f.detail && (
          <span className="mt-1 text-xs text-muted-foreground">{expanded ? '▲' : '▼'}</span>
        )}
      </button>
      {expanded && f.detail && (
        <p className="pb-3 pl-8 text-xs text-muted-foreground">{f.detail}</p>
      )}
    </div>
  )
}

// ── Overall status banner ────────────────────────────────────────────────────

function VerificationStatusBanner({ v }: { v: VerificationRecordResponse }) {
  const level = v.risk.level
  const isHigh = level === 'HIGH_RISK'
  const isMed = level === 'MEDIUM_RISK'

  const config = isHigh
    ? { label: 'Review Required', desc: 'One or more checks require admin review before a decision.', icon: '⚑', cls: 'border-status-high/50 bg-status-high-bg text-status-high' }
    : isMed
      ? { label: 'Review Recommended', desc: 'Some findings need attention. Review the evidence below.', icon: '⚠', cls: 'border-status-review/50 bg-status-review-bg text-status-review' }
      : { label: 'Checks Passed', desc: 'All verification checks passed. No significant issues detected.', icon: '✓', cls: 'border-status-clear/50 bg-status-clear-bg text-status-clear' }

  const findings = buildFindings(v)
  const issues = findings.filter((f) => f.tone === 'alert' || f.tone === 'review')

  return (
    <div className={`rounded-lg border px-4 py-3 ${config.cls}`}>
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold" aria-hidden="true">{config.icon}</span>
        <p className="text-sm font-semibold">{config.label}</p>
      </div>
      {issues.length > 0 ? (
        <ul className="mt-2 space-y-0.5 pl-1">
          {issues.map((f) => (
            <li key={f.label} className="text-xs">• {f.label}: {f.summary}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs opacity-80">{config.desc}</p>
      )}
    </div>
  )
}

// ── Decision label mapping ───────────────────────────────────────────────────

const DECISION_LABELS: Record<string, string> = {
  CLEAR: 'Identity Verified',
  SECONDARY_REVIEW: 'Re-capture Requested',
  HOLD_REFER: 'Referred for Manual Verification',
}

// ── Admin decision panel ─────────────────────────────────────────────────────

type AdminAction = 'CLEAR' | 'SECONDARY_REVIEW' | 'HOLD_REFER' | null

const RECAPTURE_REASONS = [
  'Poor lighting — retake in better light',
  'Face partially visible — ensure full face is in frame',
  'Blurry image — hold device steady and retake',
  'Incorrect document captured — recapture the correct document',
  'Face too close to edge — centre the face in frame',
  'Other',
]

function AdminDecisionPanel({
  caseId,
  onDecisionRecorded,
}: {
  caseId: string
  onDecisionRecorded: () => void
}) {
  const [action, setAction] = useState<AdminAction>(null)
  const [reason, setReason] = useState('')
  const [selectedReasons, setSelectedReasons] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submit(decision: DecisionValue, finalReason: string) {
    if (decision !== 'CLEAR' && !finalReason.trim()) {
      setError('Please provide a reason.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await decideCase(caseId, decision, finalReason || undefined)
      setAction(null)
      onDecisionRecorded()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not record decision — please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (action === 'CLEAR') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Confirm that you have reviewed the evidence and the identity is verified.
        </p>
        <textarea
          className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
          rows={2}
          placeholder="Optional reviewer note…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        {error && <p className="text-xs text-status-high">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={() => submit('CLEAR', reason)}
            disabled={saving}
            className="flex-1 rounded-md bg-status-clear px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Confirm — Verify Identity'}
          </button>
          <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary">
            Cancel
          </button>
        </div>
      </div>
    )
  }

  if (action === 'SECONDARY_REVIEW') {
    const finalReason = [...selectedReasons, ...(reason ? [reason] : [])].join('; ')
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">Select the reason(s) for requesting a re-capture:</p>
        <div className="space-y-1.5">
          {RECAPTURE_REASONS.map((r) => (
            <label key={r} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedReasons.includes(r)}
                onChange={(e) =>
                  setSelectedReasons((prev) => e.target.checked ? [...prev, r] : prev.filter((x) => x !== r))
                }
                className="accent-accent"
              />
              {r}
            </label>
          ))}
        </div>
        <textarea
          className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
          rows={2}
          placeholder="Additional notes…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        {error && <p className="text-xs text-status-high">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={() => submit('SECONDARY_REVIEW', finalReason)}
            disabled={saving || (selectedReasons.length === 0 && !reason.trim())}
            className="flex-1 rounded-md bg-status-review px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Request Re-capture'}
          </button>
          <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary">
            Cancel
          </button>
        </div>
      </div>
    )
  }

  if (action === 'HOLD_REFER') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Refer this case for manual verification. Provide a reason — this is recorded in the audit trail.
        </p>
        <textarea
          className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
          rows={3}
          placeholder="Reason for manual verification referral…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        {error && <p className="text-xs text-status-high">{error}</p>}
        <div className="flex gap-2">
          <button
            onClick={() => submit('HOLD_REFER', reason)}
            disabled={saving || !reason.trim()}
            className="flex-1 rounded-md bg-status-high px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Refer for Manual Verification'}
          </button>
          <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary">
            Cancel
          </button>
        </div>
      </div>
    )
  }

  // Default: action picker
  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={() => { setAction('CLEAR'); setReason(''); setError(null) }}
        className="flex items-center gap-2 rounded-md border border-status-clear/40 bg-status-clear-bg px-3 py-2.5 text-sm font-medium text-status-clear hover:bg-status-clear/10"
      >
        <span className="text-base font-bold">✓</span>
        <span>Verify Identity</span>
      </button>
      <button
        onClick={() => { setAction('SECONDARY_REVIEW'); setReason(''); setSelectedReasons([]); setError(null) }}
        className="flex items-center gap-2 rounded-md border border-status-review/40 bg-status-review-bg px-3 py-2.5 text-sm font-medium text-status-review hover:bg-status-review/10"
      >
        <span className="text-base">↺</span>
        <span>Request Re-capture</span>
      </button>
      <button
        onClick={() => { setAction('HOLD_REFER'); setReason(''); setError(null) }}
        className="flex items-center gap-2 rounded-md border border-status-high/40 bg-status-high-bg px-3 py-2.5 text-sm font-medium text-status-high hover:bg-status-high/10"
      >
        <span className="text-base">⚑</span>
        <span>Refer for Manual Verification</span>
      </button>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export function CaseReview() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isReviewer = user?.role === 'REVIEWER'

  const [tab, setTab] = useState<Tab>('evidence')
  const [noteText, setNoteText] = useState('')
  const [showTechDetails, setShowTechDetails] = useState(false)

  const caseQuery = useAsync(() => getCase(caseId!), [caseId])
  const identityHistory = useAsync(() => getCaseIdentityHistory(caseId!), [caseId])
  const timeline = useAsync(() => getCaseTimeline(caseId!), [caseId])

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
  const findings = v ? buildFindings(v) : []
  const awaitingDecision = c.status === 'SENT' || c.status === 'REVIEW_REQUIRED'

  return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="text-xs text-accent hover:underline">
        ← Back
      </button>

      {/* Case header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{c.case_number}</h1>
          <p className="text-sm text-muted-foreground">
            {c.traveler_name ?? 'Name not extracted'} · {c.document_type} · {c.nationality}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Checkpoint {c.checkpoint_code} · Submitted by {c.field_officer_username} ·{' '}
            {new Date(c.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          <StatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Main content — left 2 columns */}
        <div className="space-y-4 lg:col-span-2">
          {/* Tabs */}
          <div className="flex gap-1 border-b border-border">
            {(['evidence', 'identity', 'network', 'timeline'] as const).map((key) => {
              const labels: Record<Tab, string> = {
                evidence: 'Evidence',
                identity: 'Identity History',
                network: 'Network',
                timeline: 'Timeline',
              }
              return (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`px-3 py-2 text-sm font-medium ${
                    tab === key ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {labels[key]}
                </button>
              )
            })}
          </div>

          {tab === 'evidence' && (
            <div className="space-y-4">
              {v && <EvidenceImages verificationId={v.id} />}
              {/* AI Findings — plain language */}
              {v && (
                <Card title="Verification Findings">
                  <VerificationStatusBanner v={v} />
                  <div className="mt-4 divide-y divide-border">
                    {findings.map((f) => <FindingRow key={f.label} f={f} />)}
                  </div>
                  {/* Technical details — collapsed by default */}
                  <div className="mt-4 border-t border-border pt-3">
                    <button
                      className="text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setShowTechDetails((x) => !x)}
                    >
                      {showTechDetails ? '▲ Hide' : '▼ Show'} Technical Details
                    </button>
                    {showTechDetails && (
                      <div className="mt-3 space-y-2 rounded-md bg-secondary p-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          Risk Score: {v.risk.score}/100 · {v.risk.level.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-muted-foreground">{v.risk.top_reason}</p>
                        <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                          {v.risk.breakdown.map((b) => (
                            <li key={b.signal}>
                              <span className="font-medium text-foreground">{b.signal}:</span> {b.reason}{' '}
                              <span className="text-muted-foreground/60">(contribution: {(b.contribution * 100).toFixed(0)}%)</span>
                            </li>
                          ))}
                        </ul>
                        {v.validation && (
                          <>
                            <p className="mt-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                              Validation: {v.validation.status}
                            </p>
                            <ul className="space-y-0.5 text-xs text-muted-foreground">
                              {v.validation.findings.map((f) => (
                                <li key={f.check}>
                                  <span className={f.status === 'FAIL' ? 'text-status-high' : 'text-status-clear'}>
                                    [{f.status}]
                                  </span>{' '}
                                  {f.check}: {f.reason}
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </Card>
              )}
              {!v && (
                <Card>
                  <p className="text-sm text-muted-foreground">No verification data available for this case.</p>
                </Card>
              )}
            </div>
          )}

          {tab === 'identity' && (
            <Card>
              {identityHistory.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {identityHistory.data && identityHistory.data.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No matching identity found in other cases — no face cluster detected, or no live capture was taken.
                </p>
              )}
              {identityHistory.data && identityHistory.data.length > 0 && (
                <>
                  <p className="mb-3 text-xs text-status-review">
                    ⚠ Similar facial identity information was found across {identityHistory.data.length} other record(s). This is an observation for review — not a finding about the traveler.
                  </p>
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-4">Case</th>
                        <th className="py-2 pr-4">Declared Name</th>
                        <th className="py-2 pr-4">Document</th>
                        <th className="py-2 pr-4">Checkpoint</th>
                        <th className="py-2 pr-4">Match</th>
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
                            {r.similarity != null
                              ? r.similarity >= 0.75
                                ? <span className="text-status-review">Strong match ({Math.round(r.similarity * 100)}%)</span>
                                : `Similar (${Math.round(r.similarity * 100)}%)`
                              : 'Not directly compared'}
                          </td>
                          <td className="py-2 pr-4 text-muted-foreground">{r.review_status ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </Card>
          )}

          {tab === 'network' && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Connections shown here are observations recorded by the system — not accusations. Click any node to see details.
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

        {/* Sidebar — right column */}
        <div className="space-y-4">
          {/* Admin Decision Panel — REVIEWER only */}
          {isReviewer && awaitingDecision && (
            <Card title="Admin Decision">
              <p className="mb-3 text-xs text-muted-foreground">
                Review the evidence on the left, then record your decision. All decisions are permanently logged.
              </p>
              <AdminDecisionPanel caseId={c.id} onDecisionRecorded={() => caseQuery.refetch()} />
            </Card>
          )}

          {/* Officer: submit button for PENDING cases */}
          {!isReviewer && c.status === 'PENDING' && (
            <Card title="Submit Case">
              <p className="mb-2 text-xs text-muted-foreground">
                Forward this case for admin review. The admin will make the final verification decision.
              </p>
              <button
                onClick={async () => { await submitCase(c.id); caseQuery.refetch() }}
                className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                Submit for Review
              </button>
            </Card>
          )}

          {/* Decision history */}
          {c.decisions.length > 0 && (
            <Card title="Decision History">
              <ul className="space-y-2 text-sm">
                {c.decisions.map((d, i) => (
                  <li key={i} className="border-b border-border pb-2 last:border-0">
                    <p className="font-medium text-foreground">
                      {DECISION_LABELS[d.decision] ?? d.decision.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {d.officer_username} · {new Date(d.created_at).toLocaleString()}
                    </p>
                    {d.reason && <p className="mt-1 text-xs text-muted-foreground">"{d.reason}"</p>}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Notes */}
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
              className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
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
    </div>
  )
}
