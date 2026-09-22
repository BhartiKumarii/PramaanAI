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

// ── Helpers ──────────────────────────────────────────────────────────────────

function maskDocNumber(doc: string): string {
  if (!doc || doc.length <= 6) return doc
  return doc.slice(0, 3) + '****' + doc.slice(-3)
}

const DOC_TYPE_LABELS: Record<string, string> = {
  passport: 'Passport',
  visa: 'Visa',
  national_id: 'National ID / Citizenship Card',
  driving_licence: 'Driving Licence',
  driving_license: 'Driving Licence',
  permit: 'Permit / ILP',
  aadhaar: 'Aadhaar Card',
  pan_card: 'PAN Card',
  voter_id: 'Voter ID',
}

// ── Human-readable finding translation ──────────────────────────────────────

type FindingTone = 'clear' | 'review' | 'alert' | 'none'

interface FindingCard {
  label: string
  tone: FindingTone
  summary: string
  action: string
  detail?: string  // raw backend text — shown only in diagnostics
}

const SIGNAL_LABELS: Record<string, string> = {
  checksum:           'Document Validity',
  forensics:          'Document Appearance',
  face_match:         'Photo Comparison',
  face_detection:     'Live Photo Quality',
  deepfake:           'Photo Authenticity',
  liveness:           'Live Person Check',
  blacklist:          'Security Records',
  identity_graph:     'Identity Records',
  duplicate_document: 'Document History',
  citizen_registry:   'Identity Database Check',
}

const SUMMARIES: Record<string, Record<FindingTone, string>> = {
  checksum: {
    clear:  'Document data and format checks passed.',
    review: 'Some document checks require attention.',
    alert:  'Document data checks failed — the document may be expired, altered, or invalid.',
    none:   '',
  },
  forensics: {
    clear:  'No signs of alteration detected on the document.',
    review: 'Document appearance has characteristics that require physical examination.',
    alert:  'Document may have been altered — immediate review required.',
    none:   '',
  },
  face_match: {
    clear:  'The live photo is consistent with the document photo.',
    review: 'The live photo is a partial match — manual comparison recommended.',
    alert:  'The live photo does not match the document photo.',
    none:   '',
  },
  face_detection: {
    clear:  'A face was clearly detected in the live photo.',
    review: 'Face detection was uncertain — the photo may need to be retaken.',
    alert:  'No face was detected in the live photo. A new photo is required.',
    none:   '',
  },
  deepfake: {
    clear:  'The photo appears to be authentic.',
    review: 'The photo has some characteristics that require further review.',
    alert:  'The photo may not be genuine. A re-capture is recommended.',
    none:   '',
  },
  liveness: {
    clear:  'The photo was confirmed to be of a live person.',
    review: 'The live person check could not be completed — retake the photo.',
    alert:  'The photo appears to have been taken from a screen or printed image, not a live person.',
    none:   '',
  },
  blacklist: {
    clear:  'No alerts found in security records.',
    review: 'A partial security record match was found.',
    alert:  'This document is flagged in our security records.',
    none:   '',
  },
  identity_graph: {
    clear:  'No conflicting identity records found.',
    review: 'Similar identity records were found in other cases — further review recommended.',
    alert:  'A similar facial identity was found across multiple records with different document details.',
    none:   '',
  },
  duplicate_document: {
    clear:  'No previous record found for this document number.',
    review: 'This document number appeared in a previous case — review recommended.',
    alert:  'This document number has already been used in another case.',
    none:   '',
  },
  citizen_registry: {
    clear:  'Document details match our identity records.',
    review: 'Identity record found with partial information — further verification recommended.',
    alert:  'The document details do not match our identity records.',
    none:   '',
  },
}

const ACTIONS: Record<string, Record<FindingTone, string>> = {
  checksum: {
    clear: 'No action required.',
    review: 'Review the document carefully and compare all printed fields.',
    alert:  'Examine the document physically. Do not approve entry without supervisor sign-off.',
    none:   '',
  },
  forensics: {
    clear: 'No action required.',
    review: 'Examine the document in person. Look for uneven ink, mismatched fonts, or altered fields.',
    alert:  'Do not accept this document without further investigation. Refer to supervisor.',
    none:   '',
  },
  face_match: {
    clear: 'No action required.',
    review: 'Compare the person physically with the document photo. Retake photo if needed.',
    alert:  'Do not proceed. Retake the live photo. If mismatch persists, refer to supervisor immediately.',
    none:   '',
  },
  face_detection: {
    clear: 'No action required.',
    review: 'Retake the live photo in good lighting with the person facing the camera directly.',
    alert:  'Retake the live photo. Ensure only the person is visible and there is adequate lighting.',
    none:   '',
  },
  deepfake: {
    clear: 'No action required.',
    review: 'Retake the photo for a clearer image. If concern remains, refer to supervisor.',
    alert:  'Request a new live photo. If the issue persists, escalate to supervisor.',
    none:   '',
  },
  liveness: {
    clear: 'No action required.',
    review: 'Retake the live photo — ask the person to look directly at the camera.',
    alert:  'Retake the photo directly of the person. Ensure no screens or printed images are in frame.',
    none:   '',
  },
  blacklist: {
    clear: 'No action required.',
    review: 'Review the security record carefully before proceeding.',
    alert:  'Do not allow entry. Detain the traveler and notify your supervisor immediately.',
    none:   '',
  },
  identity_graph: {
    clear: 'No action required.',
    review: 'Review the related identity records. Ask if they have crossed before under a different name.',
    alert:  'Review all related records. Ask the traveler about previous crossings. Refer to supervisor.',
    none:   '',
  },
  duplicate_document: {
    clear: 'No action required.',
    review: 'Verify the document against the previous record. Check if this is the same person.',
    alert:  'Investigate the duplicate document use. Refer to supervisor.',
    none:   '',
  },
  citizen_registry: {
    clear: 'No action required.',
    review: 'Ask the traveler for additional identification to confirm their details.',
    alert:  'Ask the traveler to explain the discrepancy. Do not approve entry without supervisor sign-off.',
    none:   '',
  },
}

function translateRawReason(signal: string, reason: string): string {
  if (!reason) return ''
  const lower = reason.toLowerCase()

  // Expiry
  if (signal === 'checksum' && lower.includes('expir')) {
    const m = reason.match(/(\d{4}-\d{2}-\d{2})/)
    if (m) {
      const d = new Date(m[1])
      const fmt = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
      const daysAgo = Math.floor((Date.now() - d.getTime()) / 86400000)
      if (daysAgo > 365) {
        const y = Math.floor(daysAgo / 365)
        return `Document expired on ${fmt} — ${y} year${y > 1 ? 's' : ''} ago.`
      }
      return `Document expired on ${fmt} — ${daysAgo} day${daysAgo > 1 ? 's' : ''} ago.`
    }
    return 'Document has expired.'
  }

  // MRZ checksum
  if (signal === 'checksum' && (lower.includes('check digit') || lower.includes('mrz') || lower.includes('checksum'))) {
    if (lower.includes('valid') || lower.includes('pass')) return 'Machine-readable zone integrity confirmed.'
    return 'The machine-readable zone on this document contains an error — possible alteration.'
  }

  // Cross-field mismatch
  if (signal === 'checksum' && lower.includes('mismatch')) {
    return 'A data field on the document does not match what the machine-readable zone contains — possible alteration.'
  }

  // Face match
  if (signal === 'face_match') {
    if (lower.includes('above threshold') || lower.includes('match')) return 'Live photo is consistent with document photo.'
    if (lower.includes('below threshold')) {
      const simMatch = reason.match(/similarity\s+([\d.]+)/i)
      if (simMatch) {
        const sim = parseFloat(simMatch[1])
        if (sim >= 0.55) return `Partial match detected (${Math.round(sim * 100)}% similarity) — manual comparison recommended.`
        return `Faces do not match (${Math.round(sim * 100)}% similarity) — possible different person.`
      }
      return 'Live photo does not meet the match threshold — possible different person.'
    }
  }

  // Identity cluster
  if (signal === 'identity_graph' && lower.includes('cluster')) {
    const m = reason.match(/(\d+)\s+face/i)
    const count = m ? m[1] : 'multiple'
    return `Similar facial identity found in ${count} other record(s). The same person may have crossed using different documents.`
  }

  // Forensics
  if (signal === 'forensics') {
    if (lower.includes('hologram') || lower.includes('security feature')) return 'A security feature on the document appears to be missing or altered.'
    if (lower.includes('opacity') || lower.includes('ink') || lower.includes('stamp')) return 'Ink or stamp patterns appear inconsistent with a genuine document.'
    if (lower.includes('character') || lower.includes('alignment') || lower.includes('text edit')) return 'Text on the document appears to have been altered — characters are misaligned.'
    if (lower.includes('font')) return 'Font inconsistencies detected — the document may not be genuine.'
    return 'Document appearance has characteristics that require physical examination.'
  }

  // Deepfake
  if (signal === 'deepfake') {
    const m = reason.match(/probability[:\s]+([\d.]+)/i)
    if (m) {
      const prob = parseFloat(m[1])
      if (prob > 0.7) return `Photo authenticity concern detected (${Math.round(prob * 100)}% confidence). The image may not be genuine.`
      if (prob > 0.35) return `Photo has some characteristics requiring review (${Math.round(prob * 100)}% confidence).`
      return 'Photo appears to be authentic.'
    }
  }

  // Liveness
  if (signal === 'liveness') {
    if (lower.includes('artificial') || lower.includes('spoof')) return 'The photo may have been taken from a screen or printed image.'
    if (lower.includes('live')) return 'Live person confirmed.'
  }

  // Watchlist
  if (signal === 'blacklist') {
    if (lower.includes('no match') || lower.includes('no hit') || lower.includes('no_hit')) return 'No alerts found in security records.'
    if (lower.includes('hit') || lower.includes('match') || lower.includes('found')) return 'Security alert: this document is flagged in our records.'
  }

  // Citizen registry
  if (signal === 'citizen_registry') {
    if (lower.includes('match') && !lower.includes('mis')) return 'Document details match our identity records.'
    if (lower.includes('mismatch') || lower.includes('differ')) return 'The document details do not match our records.'
    if (lower.includes('revok') || lower.includes('cancel')) return 'This document has been cancelled or revoked.'
    if (lower.includes('no record') || lower.includes('not found')) return 'No matching record found in our identity database.'
    if (lower.includes('expir')) return 'This document is recorded as expired in our database.'
  }

  return reason  // fallback — raw
}

function signalToFinding(signal: string, rawRisk: number, reason: string): FindingCard {
  const label = SIGNAL_LABELS[signal] ?? signal.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  // More realistic thresholds: only flag genuine issues, not every minor anomaly
  const tone: FindingTone = rawRisk >= 0.7 ? 'alert' : rawRisk >= 0.4 ? 'review' : 'clear'
  const s = SUMMARIES[signal]
  const a = ACTIONS[signal]
  const summary = s ? s[tone] : tone === 'clear' ? 'Check passed.' : tone === 'review' ? 'Requires review.' : 'Issue detected.'
  const action = a ? a[tone] : 'Consult your supervisor.'
  const translatedDetail = translateRawReason(signal, reason)

  // Include actual risk score in detail for transparency
  const riskPercent = Math.round(rawRisk * 100)
  const detailWithScore = rawRisk > 0 && tone !== 'clear'
    ? `${translatedDetail} (${riskPercent}% risk score)`
    : translatedDetail

  return { label, tone, summary, action, detail: detailWithScore }
}

function buildFindings(v: VerificationRecordResponse): FindingCard[] {
  const findings: FindingCard[] = []
  for (const b of v.risk.breakdown) {
    if (b.raw_risk > 0 || b.signal === 'blacklist' || b.signal === 'duplicate_document' || b.signal === 'citizen_registry') {
      findings.push(signalToFinding(b.signal, b.raw_risk, b.reason))
    }
  }
  const presentSignals = new Set(findings.map((f) => f.label))
  if (!presentSignals.has(SIGNAL_LABELS.blacklist) && v.registry) {
    findings.push(signalToFinding('blacklist', v.registry.status === 'HIT' ? 0.9 : 0,
      v.registry.status === 'HIT' ? 'Security alert found.' : 'No matching security record found.'))
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
    clear:  { icon: '✓', text: 'text-status-clear',  bg: 'bg-status-clear-bg'  },
    review: { icon: '⚠', text: 'text-status-review', bg: 'bg-status-review-bg' },
    alert:  { icon: '✕', text: 'text-status-high',   bg: 'bg-status-high-bg'   },
    none:   { icon: '–', text: 'text-muted-foreground', bg: 'bg-secondary'      },
  }
  const s = toneStyles[f.tone]
  return (
    <div className="border-b border-border last:border-0">
      <button
        className="flex w-full items-start gap-3 py-3 text-left"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${s.bg} ${s.text}`}>
          {s.icon}
        </span>
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">{f.label}</p>
          <p className="text-xs text-muted-foreground">{f.summary}</p>
        </div>
        <span className="mt-1 text-xs text-muted-foreground">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="space-y-2 pb-3 pl-8">
          {f.tone !== 'clear' && (
            <div className={`rounded-md px-3 py-2 text-xs ${s.bg}`}>
              <p className={`font-semibold ${s.text}`}>Recommended action</p>
              <p className="mt-0.5 text-foreground">{f.action}</p>
            </div>
          )}
          {f.detail && f.detail !== f.summary && (
            <p className="text-xs text-muted-foreground">{f.detail}</p>
          )}
        </div>
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
    ? { label: 'Review Required', icon: '⚑', cls: 'border-status-high/50 bg-status-high-bg text-status-high' }
    : isMed
      ? { label: 'Review Recommended', icon: '⚠', cls: 'border-status-review/50 bg-status-review-bg text-status-review' }
      : { label: 'All Checks Passed', icon: '✓', cls: 'border-status-clear/50 bg-status-clear-bg text-status-clear' }

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
        <p className="mt-1 text-xs opacity-80">No issues detected. Verification can proceed.</p>
      )}
    </div>
  )
}

// ── Decision & timeline labels ───────────────────────────────────────────────

const DECISION_LABELS: Record<string, string> = {
  CLEAR:            'Identity Verified',
  SECONDARY_REVIEW: 'Re-capture Requested',
  HOLD_REFER:       'Referred for Manual Verification',
}

const TIMELINE_LABELS: Record<string, string> = {
  CREATED:                     'Document scanned and analyzed',
  VIEWED:                      'Case opened for review',
  SENT:                        'Case submitted for admin review',
  DECISION_CLEAR:              'Identity verified by reviewer',
  DECISION_SECONDARY_REVIEW:  'Re-capture requested by reviewer',
  DECISION_HOLD_REFER:         'Referred for manual verification by reviewer',
  NOTE_ADDED:                  'Note added',
}

// ── Admin decision panel ─────────────────────────────────────────────────────

type AdminAction = 'CLEAR' | 'SECONDARY_REVIEW' | 'HOLD_REFER' | null

const RECAPTURE_REASONS = [
  'Poor lighting — retake in better light',
  'Face partially visible — ensure full face is in frame',
  'Blurry image — hold device steady and retake',
  'Incorrect document captured — recapture the correct document',
  'Face too close to edge — centre the face in frame',
  'Photo taken from screen or printed image — retake in person',
  'Other',
]

function AdminDecisionPanel({ caseId, onDecisionRecorded }: { caseId: string; onDecisionRecorded: () => void }) {
  const [action, setAction] = useState<AdminAction>(null)
  const [reason, setReason] = useState('')
  const [selectedReasons, setSelectedReasons] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submit(decision: DecisionValue, finalReason: string) {
    if (decision !== 'CLEAR' && !finalReason.trim()) { setError('Please provide a reason.'); return }
    setSaving(true); setError(null)
    try {
      await decideCase(caseId, decision, finalReason || undefined)
      setAction(null); onDecisionRecorded()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not record decision — please try again.')
    } finally { setSaving(false) }
  }

  if (action === 'CLEAR') return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Confirm that you have reviewed all evidence and the identity is verified.</p>
      <textarea className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none" rows={2}
        placeholder="Optional reviewer note…" value={reason} onChange={(e) => setReason(e.target.value)} />
      {error && <p className="text-xs text-status-high">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => submit('CLEAR', reason)} disabled={saving}
          className="flex-1 rounded-md bg-status-clear px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {saving ? 'Saving…' : 'Confirm — Verify Identity'}
        </button>
        <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary">Cancel</button>
      </div>
    </div>
  )

  if (action === 'SECONDARY_REVIEW') {
    const finalReason = [...selectedReasons, ...(reason ? [reason] : [])].join('; ')
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">Select the reason(s) why a new photo or document is needed:</p>
        <div className="space-y-1.5">
          {RECAPTURE_REASONS.map((r) => (
            <label key={r} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={selectedReasons.includes(r)} className="accent-accent"
                onChange={(e) => setSelectedReasons((prev) => e.target.checked ? [...prev, r] : prev.filter((x) => x !== r))} />
              {r}
            </label>
          ))}
        </div>
        <textarea className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
          rows={2} placeholder="Additional details…" value={reason} onChange={(e) => setReason(e.target.value)} />
        {error && <p className="text-xs text-status-high">{error}</p>}
        <div className="flex gap-2">
          <button onClick={() => submit('SECONDARY_REVIEW', finalReason)}
            disabled={saving || (selectedReasons.length === 0 && !reason.trim())}
            className="flex-1 rounded-md bg-status-review px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50">
            {saving ? 'Saving…' : 'Request Re-capture'}
          </button>
          <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary">Cancel</button>
        </div>
      </div>
    )
  }

  if (action === 'HOLD_REFER') return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Refer for manual verification. Provide a reason — this is permanently recorded.</p>
      <textarea className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
        rows={3} placeholder="Reason for manual verification referral…" value={reason} onChange={(e) => setReason(e.target.value)} />
      {error && <p className="text-xs text-status-high">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => submit('HOLD_REFER', reason)} disabled={saving || !reason.trim()}
          className="flex-1 rounded-md bg-status-high px-3 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {saving ? 'Saving…' : 'Refer for Manual Verification'}
        </button>
        <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary">Cancel</button>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-2">
      <button onClick={() => { setAction('CLEAR'); setReason(''); setError(null) }}
        className="flex items-center gap-2 rounded-md border border-status-clear/40 bg-status-clear-bg px-3 py-2.5 text-sm font-medium text-status-clear hover:bg-status-clear/10">
        <span className="text-base font-bold">✓</span><span>Verify Identity</span>
      </button>
      <button onClick={() => { setAction('SECONDARY_REVIEW'); setReason(''); setSelectedReasons([]); setError(null) }}
        className="flex items-center gap-2 rounded-md border border-status-review/40 bg-status-review-bg px-3 py-2.5 text-sm font-medium text-status-review hover:bg-status-review/10">
        <span className="text-base">↺</span><span>Request Re-capture</span>
      </button>
      <button onClick={() => { setAction('HOLD_REFER'); setReason(''); setError(null) }}
        className="flex items-center gap-2 rounded-md border border-status-high/40 bg-status-high-bg px-3 py-2.5 text-sm font-medium text-status-high hover:bg-status-high/10">
        <span className="text-base">⚑</span><span>Refer for Manual Verification</span>
      </button>
    </div>
  )
}

// ── Detail field (single-column key-value row) ──────────────────────────

function DetailField({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  if (!value) return null
  return (
    <div className="flex items-baseline justify-between py-1.5 border-b border-border/50 last:border-0">
      <span className="text-xs text-muted-foreground shrink-0 w-36">{label}</span>
      <span className={`text-sm text-foreground text-right ${mono ? 'font-mono' : ''} whitespace-pre-line`}>{value}</span>
    </div>
  )
}

// ── Humanize technical reason text ──────────────────────────────────────

function humanizeReason(raw: string | null | undefined): string {
  if (!raw) return ''
  let text = raw

  text = text.replace(/Multi-identity cluster detected\s*—?\s*/gi, '')
  text = text.replace(/\d+\s+face embeddings? directly matched\s*\(similarity\s*>=?\s*[\d.]+\)\s*spanning\s*(\d+)\s*distinct declared name\(s\)\s*and\s*(\d+)\s*distinct document number\(s\)/gi,
    (_, names, docs) => `Same face matched across ${names} different name(s) and ${docs} different document(s)`)
  text = text.replace(/cosine similarity\s*[\d.]+\s*vs\s*match threshold\s*[\d.]+:\s*above threshold,?\s*match/gi,
    'Live photo matches the document photo')
  text = text.replace(/cosine similarity\s*([\d.]+)\s*vs\s*match threshold\s*[\d.]+:\s*below threshold/gi,
    (_, sim) => `Live photo does not match document photo (${Math.round(parseFloat(sim) * 100)}% similarity)`)
  text = text.replace(/Single-frame analysis:\s*sharpness=[\d.]+,\s*uniformity=[\d.]+,\s*screen artifacts=[\d.]+\.?\s*Multi-frame analysis recommended for higher confidence\.?/gi,
    'Photo quality check completed — multi-angle verification recommended for higher confidence')
  text = text.replace(/\d+\s+faces? detected in the image \(expected exactly one\)/gi,
    'Multiple faces detected in the photo — only one person should be visible')
  text = text.replace(/no date_of_expiry field was extracted from the document/gi,
    'Expiry date could not be read from the document')
  text = text.replace(/no date_of_birth field was extracted from the document/gi,
    'Date of birth could not be read from the document')
  text = text.replace(/hard override:\s*/gi, '')
  text = text.replace(/rawRisk/g, 'risk level')
  text = text.replace(/\bela\b/gi, 'image analysis')

  text = text.replace(/Document checks:\s*expiry:\s*/gi, 'Document expiry: ')
  text = text.replace(/Identity graph:\s*/gi, 'Identity records: ')
  text = text.replace(/Face in live capture:\s*/gi, 'Live photo: ')
  text = text.replace(/Liveness \/ spoof:\s*/gi, 'Liveness check: ')
  text = text.replace(/Face match:\s*/gi, 'Photo comparison: ')

  text = text.replace(/;\s*Identity records:.*?(?=;|$)/g, (match, offset) => {
    if (offset > 0 && text.slice(0, offset).includes('Identity records:')) return ''
    return match
  })

  return text.trim()
}

// ── Main component ───────────────────────────────────────────────────────────

export function CaseReview() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isReviewer = user?.role === 'REVIEWER'

  const [tab, setTab] = useState<Tab>('evidence')
  const [noteText, setNoteText] = useState('')
  const [showDiagnostics, setShowDiagnostics] = useState(false)

  const caseQuery = useAsync(() => getCase(caseId!), [caseId])
  const identityHistory = useAsync(() => getCaseIdentityHistory(caseId!), [caseId])
  const timeline = useAsync(() => getCaseTimeline(caseId!), [caseId])

  const [noteLoading, setNoteLoading] = useState(false)
  const [noteError, setNoteError] = useState('')

  async function handleAddNote() {
    if (!noteText.trim()) return
    setNoteLoading(true)
    setNoteError('')
    try {
      await addCaseNote(caseId!, noteText)
      setNoteText('')
      caseQuery.refetch()
    } catch (e: unknown) {
      setNoteError(e instanceof Error ? e.message : 'Failed to add note')
    } finally {
      setNoteLoading(false)
    }
  }

  if (caseQuery.loading) return <p className="text-sm text-muted-foreground">Loading case…</p>
  if (caseQuery.error) return <p className="text-sm text-status-high">{caseQuery.error}</p>
  const c = caseQuery.data
  if (!c) return null

  const v = c.verification
  const findings = v ? buildFindings(v) : []
  const awaitingDecision = c.status === 'SENT' || c.status === 'REVIEW_REQUIRED'

  // Extract useful OCR fields for the identity card
  const ocr = v?.ocr?.fields ?? {}
  const docNumber = ocr.passport_number ?? ocr.license_number ?? ocr.document_number ?? ocr.visa_number ?? ocr.permit_number ?? null
  const displayDocType = DOC_TYPE_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type

  return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="text-xs text-accent hover:underline">← Back to cases</button>

      {/* ── Identity card header — single column layout ── */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Case {c.case_number}</p>
            <h1 className="text-2xl font-bold text-foreground mt-1">
              {c.traveler_name ?? ocr.name ?? 'Name not extracted'}
            </h1>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <StatusBadge status={c.status} />
            <PriorityBadge priority={c.priority} />
            {v && (
              <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                v.risk.level === 'HIGH_RISK'
                  ? 'bg-status-high-bg text-status-high border-status-high/30'
                  : v.risk.level === 'MEDIUM_RISK'
                    ? 'bg-status-review-bg text-status-review border-status-review/30'
                    : 'bg-status-clear-bg text-status-clear border-status-clear/30'
              }`}>
                <span aria-hidden="true">{v.risk.level === 'HIGH_RISK' ? '⚑' : v.risk.level === 'MEDIUM_RISK' ? '⚠' : '✓'}</span>
                {v.risk.level === 'HIGH_RISK' ? 'High Risk' : v.risk.level === 'MEDIUM_RISK' ? 'Medium Risk' : 'Low Risk'}
                {v.risk.score != null && <span className="ml-1 opacity-75">({Math.round(v.risk.score * 100)}%)</span>}
              </span>
            )}
          </div>
        </div>

        {/* Single-column extracted document details */}
        <div className="grid grid-cols-1 gap-0 border-t border-border pt-3">
          <DetailField label="Document Type" value={displayDocType} />
          {docNumber && <DetailField label="Document Number" value={maskDocNumber(docNumber)} mono />}
          <DetailField label="Nationality" value={c.nationality || ocr.nationality} />
          {ocr.date_of_birth && <DetailField label="Date of Birth" value={ocr.date_of_birth} />}
          {ocr.date_of_expiry && <DetailField label="Date of Expiry" value={ocr.date_of_expiry} />}
          {ocr.date_of_issue && <DetailField label="Date of Issue" value={ocr.date_of_issue} />}
          {ocr.gender && /^(m|f|male|female|other|transgender)$/i.test(ocr.gender.trim()) && (
            <DetailField label="Gender" value={ocr.gender.trim().charAt(0).toUpperCase() === 'M' ? 'Male' : ocr.gender.trim().charAt(0).toUpperCase() === 'F' ? 'Female' : ocr.gender.trim()} />
          )}
          {ocr.place_of_birth && <DetailField label="Place of Birth" value={ocr.place_of_birth} />}
          {ocr.place_of_issue && <DetailField label="Place of Issue" value={ocr.place_of_issue} />}
          {ocr.issuing_authority && <DetailField label="Issuing Authority" value={ocr.issuing_authority} />}
          {ocr.mrz_line1 && <DetailField label="MRZ" value={`${ocr.mrz_line1}${ocr.mrz_line2 ? '\n' + ocr.mrz_line2 : ''}`} mono />}
          {ocr.voter_id && <DetailField label="Voter ID" value={ocr.voter_id} mono />}
          {ocr.aadhaar_number && <DetailField label="Aadhaar" value={ocr.aadhaar_number} mono />}
          {ocr.father_name && <DetailField label="Father's Name" value={ocr.father_name} />}
          {ocr.address && <DetailField label="Address" value={ocr.address} />}
          <div className="border-t border-border mt-2 pt-2">
            <DetailField label="Checkpoint" value={c.checkpoint_code} />
            <DetailField label="Submitted by" value={c.field_officer_username} />
            <DetailField label="Screened at" value={new Date(c.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* ── Main content — left 2 columns ── */}
        <div className="space-y-4 lg:col-span-2">
          <div className="flex gap-1 border-b border-border">
            {(['evidence', 'identity', 'network', 'timeline'] as const).map((key) => {
              const labels: Record<Tab, string> = {
                evidence: 'Evidence & Findings',
                identity: 'Identity History',
                network:  'Connections',
                timeline: 'Case Timeline',
              }
              return (
                <button key={key} onClick={() => setTab(key)}
                  className={`px-3 py-2 text-sm font-medium ${tab === key ? 'border-b-2 border-accent text-accent' : 'text-muted-foreground hover:text-foreground'}`}>
                  {labels[key]}
                </button>
              )
            })}
          </div>

          {tab === 'evidence' && (
            <div className="space-y-4">
              {/* Evidence images */}
              {v ? (
                <EvidenceImages verificationId={v.id} caseCreatedAt={c.created_at} />
              ) : (
                <Card>
                  <p className="text-sm text-muted-foreground">No document or photo captured for this case.</p>
                </Card>
              )}

              {/* Verification findings */}
              {v ? (
                <Card title="Verification Findings">
                  <VerificationStatusBanner v={v} />
                  <div className="mt-4 divide-y divide-border">
                    {findings.map((f) => <FindingRow key={f.label} f={f} />)}
                  </div>
                  {/* System diagnostics — clearly labelled */}
                  <div className="mt-4 border-t border-border pt-3">
                    <button className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setShowDiagnostics((x) => !x)}>
                      <span>{showDiagnostics ? '▲' : '▶'}</span>
                      <span className="uppercase tracking-wide">System Diagnostics — Internal Use Only</span>
                    </button>
                    {showDiagnostics && (
                      <div className="mt-3 rounded-md bg-secondary/60 p-3 space-y-2">
                        <p className="text-xs italic text-muted-foreground">Raw AI/ML output. Not for use in officer or admin decisions.</p>
                        <p className="text-xs font-semibold text-muted-foreground">
                          Risk Score: {v.risk.score}/100 · {v.risk.level.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-muted-foreground">{v.risk.top_reason}</p>
                        <ul className="space-y-1 text-xs text-muted-foreground">
                          {v.risk.breakdown.map((b) => (
                            <li key={b.signal}>
                              <span className="font-medium text-foreground">{b.signal}:</span> {b.reason}{' '}
                              <span className="opacity-60">(contribution: {(b.contribution * 100).toFixed(0)}%)</span>
                            </li>
                          ))}
                        </ul>
                        {v.validation && (
                          <>
                            <p className="text-xs font-semibold text-muted-foreground">Validation: {v.validation.status}</p>
                            <ul className="space-y-0.5 text-xs text-muted-foreground">
                              {v.validation.findings.map((f) => (
                                <li key={f.check}>
                                  <span className={f.status === 'FAIL' ? 'text-status-high' : 'text-status-clear'}>[{f.status}]</span>{' '}
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
              ) : (
                <Card><p className="text-sm text-muted-foreground">No verification data available for this case.</p></Card>
              )}
            </div>
          )}

          {tab === 'identity' && (
            <Card>
              {identityHistory.loading && <p className="text-sm text-muted-foreground">Loading identity history…</p>}
              {identityHistory.data && identityHistory.data.length === 0 && (
                <div className="py-4 text-center space-y-2">
                  <p className="text-2xl">🪪</p>
                  <p className="text-sm font-medium text-foreground">No prior crossing records</p>
                  <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                    No other cases share a similar facial identity with this record. This appears to be a first-time or new entry — no biometric history available.
                  </p>
                </div>
              )}
              {identityHistory.data && identityHistory.data.length > 0 && (
                <>
                  <div className="mb-5 rounded-lg border border-status-review/40 bg-status-review-bg px-4 py-3 text-sm text-status-review">
                    <p className="font-semibold">⚠ {identityHistory.data.length} prior crossing record(s) found</p>
                    <p className="mt-1 text-xs">
                      These cases share similar facial characteristics with this person. Review each entry to confirm consistent identity.
                    </p>
                  </div>
                  {/* Timeline view */}
                  <ol className="relative border-l-2 border-border space-y-0">
                    {[...identityHistory.data]
                      .sort((a, b) => new Date(b.occurred_at ?? 0).getTime() - new Date(a.occurred_at ?? 0).getTime())
                      .map((r, i) => {
                        const isStrong = (r.similarity ?? 0) >= 0.75
                        return (
                          <li key={r.record_id ?? i} className="ml-4 pb-6">
                            <div className="absolute -left-[9px] mt-1 h-4 w-4 rounded-full border-2 border-border bg-card flex items-center justify-center">
                              <div className={`h-1.5 w-1.5 rounded-full ${isStrong ? 'bg-status-review' : 'bg-muted-foreground'}`} />
                            </div>
                            <div className="rounded-lg border border-border bg-secondary/30 p-3 space-y-2">
                              <div className="flex items-center justify-between flex-wrap gap-2">
                                <span className="font-mono text-xs font-semibold text-foreground bg-secondary px-2 py-0.5 rounded border border-border">
                                  {r.case_number ?? '—'}
                                </span>
                                {r.similarity != null ? (
                                  <span className={`text-xs font-medium ${isStrong ? 'text-status-review' : 'text-muted-foreground'}`}>
                                    {isStrong ? '⚠ Strong match' : 'Partial match'} · {Math.round(r.similarity * 100)}%
                                  </span>
                                ) : (
                                  <span className="text-xs text-muted-foreground">Not directly compared</span>
                                )}
                              </div>
                              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                                <div><span className="text-muted-foreground">Name on record: </span><span className="font-medium text-foreground">{r.declared_name}</span></div>
                                <div><span className="text-muted-foreground">Document: </span><span className="text-foreground">{r.masked_document_number ?? '—'}</span></div>
                                <div><span className="text-muted-foreground">Checkpoint: </span><span className="text-foreground">{r.checkpoint_code ?? '—'}</span></div>
                                <div><span className="text-muted-foreground">Status: </span><span className="text-foreground">{r.review_status ?? '—'}</span></div>
                              </div>
                              {r.occurred_at && (
                                <p className="text-xs text-muted-foreground">
                                  Screened: {new Date(r.occurred_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                </p>
                              )}
                            </div>
                          </li>
                        )
                      })}
                  </ol>
                </>
              )}
            </Card>
          )}

          {tab === 'network' && (
            <div className="space-y-3">
              <Card>
                <p className="mb-1 text-sm font-medium text-foreground">Identity & Travel Connections</p>
                <p className="text-xs text-muted-foreground">
                  This view shows relationships the system recorded between people, documents, checkpoints, and travel events.
                  A connection here is an observation — not an accusation. Use it as supporting context when reviewing the case.
                </p>
              </Card>
              <CaseNetworkPanel caseId={c.id} />
            </div>
          )}

          {tab === 'timeline' && (
            <Card title="Case Timeline">
              {timeline.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {timeline.data && timeline.data.length === 0 && (
                <p className="text-sm text-muted-foreground">No events recorded for this case yet.</p>
              )}
              {timeline.data && timeline.data.length > 0 && (
                <ol className="space-y-4 border-l-2 border-border pl-4">
                  {timeline.data.map((event, i) => {
                    const label = TIMELINE_LABELS[event.event_type] ?? event.action
                    const dotColor = event.event_type?.includes('CLEAR') ? 'bg-status-clear border-status-clear/50'
                      : event.event_type?.includes('HOLD') || event.event_type?.includes('FLAG') ? 'bg-status-high border-status-high/50'
                      : event.event_type?.includes('REVIEW') || event.event_type?.includes('SENT') ? 'bg-status-review border-status-review/50'
                      : 'bg-accent border-accent/50'
                    return (
                      <li key={i} className="relative">
                        <div className={`absolute -left-[1.3rem] mt-1 h-3 w-3 rounded-full border-2 ${dotColor}`} />
                        <p className="text-xs text-muted-foreground">{new Date(event.created_at).toLocaleString()}</p>
                        <p className="text-sm font-medium text-foreground">{label}</p>
                        {event.actor_username && (
                          <p className="text-xs text-muted-foreground">by {event.actor_username}</p>
                        )}
                        {event.detail && (
                          <p className="mt-1 rounded bg-secondary px-2 py-1.5 text-xs text-muted-foreground leading-relaxed">
                            {humanizeReason(event.detail)}
                          </p>
                        )}
                      </li>
                    )
                  })}
                </ol>
              )}
            </Card>
          )}
        </div>

        {/* ── Sidebar ── */}
        <div className="space-y-4">
          {isReviewer && awaitingDecision && (
            <Card title="Verification Decision">
              <p className="mb-3 text-xs text-muted-foreground">
                Review all evidence on the left before recording your decision. Every decision is permanently logged.
              </p>
              <AdminDecisionPanel caseId={c.id} onDecisionRecorded={() => caseQuery.refetch()} />
            </Card>
          )}

          {!isReviewer && c.status === 'PENDING' && (
            <Card title="Submit for Review">
              <p className="mb-2 text-xs text-muted-foreground">
                Forward this case to the admin review queue. The reviewer will examine the evidence and make the final decision.
              </p>
              <button
                onClick={async () => { await submitCase(c.id); caseQuery.refetch() }}
                className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
                Submit for Review
              </button>
            </Card>
          )}

          {c.decisions.length > 0 && (
            <Card title="Decision History">
              <ul className="space-y-3 text-sm">
                {c.decisions.map((d, i) => {
                  const isClear = d.decision === 'CLEAR'
                  const isHold = d.decision === 'HOLD_REFER'
                  const icon = isClear ? '✓' : isHold ? '⚑' : '⚠'
                  const accentClass = isClear ? 'text-status-clear' : isHold ? 'text-status-high' : 'text-status-review'
                  const bgClass = isClear ? 'bg-status-clear/5 border-status-clear/20' : isHold ? 'bg-status-high/5 border-status-high/20' : 'bg-status-review/5 border-status-review/20'
                  return (
                    <li key={i} className={`rounded-lg border p-3 ${bgClass}`}>
                      <div className="flex items-center gap-2">
                        <span className={`text-base ${accentClass}`}>{icon}</span>
                        <p className={`font-semibold ${accentClass}`}>
                          {DECISION_LABELS[d.decision] ?? d.decision.replace(/_/g, ' ')}
                        </p>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Recorded by {d.officer_username ?? 'reviewer'} · {new Date(d.created_at).toLocaleString()}
                      </p>
                      {d.reason && (
                        <p className="mt-2 rounded bg-secondary px-2 py-1.5 text-xs text-muted-foreground leading-relaxed">
                          {humanizeReason(d.reason)}
                        </p>
                      )}
                    </li>
                  )
                })}
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
                  <p className="mt-1 whitespace-pre-line text-sm">{n.note}</p>
                </li>
              ))}
              {c.notes.length === 0 && <p className="text-sm text-muted-foreground">No notes yet.</p>}
            </ul>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-muted-foreground">Add a note</span>
              <button
                onClick={() => {
                  // Auto-generate a human-readable note from case data
                  const risk = v?.risk
                  const checkpoint = c.checkpoint_code ?? 'this checkpoint'
                  const docType = DOC_TYPE_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type ?? 'document'
                  const nat = c.nationality ?? ''
                  const riskLevel = risk?.level === 'HIGH_RISK' ? 'High risk' : risk?.level === 'MEDIUM_RISK' ? 'Medium risk' : 'Low risk'
                  // Humanise top reason
                  let reason = humanizeReason(risk?.top_reason ?? '')
                  if (reason.length > 120) reason = reason.slice(0, 120) + '…'
                  const actionMap: Record<string, string> = {
                    HIGH_RISK: 'Entry not recommended without supervisor approval. Refer to senior officer immediately.',
                    MEDIUM_RISK: 'Secondary review recommended before permitting entry.',
                    LOW_RISK: 'No issues detected. Document appears valid.',
                  }
                  const action = actionMap[risk?.level ?? ''] ?? 'Further review recommended.'
                  const generated = `Document reviewed at ${checkpoint}. ${riskLevel} — ${docType}${nat ? ` (${nat})` : ''}. ${reason ? reason + '. ' : ''}${action}`
                  setNoteText(generated)
                }}
                className="text-xs text-accent hover:text-accent/80 border border-accent/30 px-2 py-0.5 rounded hover:bg-accent/10 transition-colors"
              >
                ✨ Generate note
              </button>
            </div>
            <textarea
              className="w-full rounded-md border border-border bg-background p-2 text-sm focus:border-ring focus:outline-none"
              rows={3} placeholder="Add a note…" value={noteText}
              onChange={(e) => setNoteText(e.target.value)} />
            {noteError && <p className="mt-1 text-xs text-status-high">{noteError}</p>}
            <button onClick={handleAddNote} disabled={noteLoading || !noteText.trim()}
              className="mt-2 w-full rounded-md border border-border py-1.5 text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-50">
              {noteLoading ? 'Saving…' : 'Add Note'}
            </button>
          </Card>
        </div>
      </div>
    </div>
  )
}
