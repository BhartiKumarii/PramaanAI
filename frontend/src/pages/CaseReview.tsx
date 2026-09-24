import { useState } from 'react'
import { DocVerifyCasePanel } from '../components/DocVerifyCasePanel'
import { suggestAction, type ActionSuggestion } from '../lib/suggestAction'
import type { VerificationOutcome } from '../api/docverify'
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

type Tab = 'overview' | 'evidence' | 'risk' | 'timeline' | 'history'

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
  detail?: string
  category?: 'document' | 'identity' | 'security'
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

const SIGNAL_CATEGORY: Record<string, 'document' | 'identity' | 'security'> = {
  checksum: 'document',
  forensics: 'document',
  face_match: 'identity',
  face_detection: 'identity',
  deepfake: 'identity',
  liveness: 'identity',
  blacklist: 'security',
  identity_graph: 'security',
  duplicate_document: 'security',
  citizen_registry: 'identity',
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

  if (signal === 'checksum' && (lower.includes('check digit') || lower.includes('mrz') || lower.includes('checksum'))) {
    if (lower.includes('valid') || lower.includes('pass')) return 'Machine-readable zone integrity confirmed.'
    return 'The machine-readable zone on this document contains an error — possible alteration.'
  }

  if (signal === 'checksum' && lower.includes('mismatch')) {
    return 'A data field on the document does not match what the machine-readable zone contains — possible alteration.'
  }

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

  if (signal === 'identity_graph' && lower.includes('cluster')) {
    const m = reason.match(/(\d+)\s+face/i)
    const count = m ? m[1] : 'multiple'
    return `Similar facial identity found in ${count} other record(s). The same person may have crossed using different documents.`
  }

  if (signal === 'forensics') {
    if (lower.includes('hologram') || lower.includes('security feature')) return 'A security feature on the document appears to be missing or altered.'
    if (lower.includes('opacity') || lower.includes('ink') || lower.includes('stamp')) return 'Ink or stamp patterns appear inconsistent with a genuine document.'
    if (lower.includes('character') || lower.includes('alignment') || lower.includes('text edit')) return 'Text on the document appears to have been altered — characters are misaligned.'
    if (lower.includes('font')) return 'Font inconsistencies detected — the document may not be genuine.'
    return 'Document appearance has characteristics that require physical examination.'
  }

  if (signal === 'deepfake') {
    const m = reason.match(/probability[:\s]+([\d.]+)/i)
    if (m) {
      const prob = parseFloat(m[1])
      if (prob > 0.7) return `Photo authenticity concern detected (${Math.round(prob * 100)}% confidence). The image may not be genuine.`
      if (prob > 0.35) return `Photo has some characteristics requiring review (${Math.round(prob * 100)}% confidence).`
      return 'Photo appears to be authentic.'
    }
  }

  if (signal === 'liveness') {
    if (lower.includes('artificial') || lower.includes('spoof')) return 'The photo may have been taken from a screen or printed image.'
    if (lower.includes('live')) return 'Live person confirmed.'
  }

  if (signal === 'blacklist') {
    if (lower.includes('no match') || lower.includes('no hit') || lower.includes('no_hit')) return 'No alerts found in security records.'
    if (lower.includes('hit') || lower.includes('match') || lower.includes('found')) return 'Security alert: this document is flagged in our records.'
  }

  if (signal === 'citizen_registry') {
    if (lower.includes('match') && !lower.includes('mis')) return 'Document details match our identity records.'
    if (lower.includes('mismatch') || lower.includes('differ')) return 'The document details do not match our records.'
    if (lower.includes('revok') || lower.includes('cancel')) return 'This document has been cancelled or revoked.'
    if (lower.includes('no record') || lower.includes('not found')) return 'No matching record found in our identity database.'
    if (lower.includes('expir')) return 'This document is recorded as expired in our database.'
  }

  return reason
}

function signalToFinding(signal: string, rawRisk: number, reason: string): FindingCard {
  const label = SIGNAL_LABELS[signal] ?? signal.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  const tone: FindingTone = rawRisk >= 0.7 ? 'alert' : rawRisk >= 0.4 ? 'review' : 'clear'
  const s = SUMMARIES[signal]
  const a = ACTIONS[signal]
  const summary = s ? s[tone] : tone === 'clear' ? 'Check passed.' : tone === 'review' ? 'Requires review.' : 'Issue detected.'
  const action = a ? a[tone] : 'Consult your supervisor.'
  const translatedDetail = translateRawReason(signal, reason)
  const riskPercent = Math.round(rawRisk * 100)
  const detailWithScore = rawRisk > 0 && tone !== 'clear'
    ? `${translatedDetail} (${riskPercent}% risk score)`
    : translatedDetail
  const category = SIGNAL_CATEGORY[signal] ?? 'document'

  return { label, tone, summary, action, detail: detailWithScore, category }
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

type AdminAction = 'CLEAR' | 'SECONDARY_REVIEW' | 'HOLD_REFER' | 'ESCALATE' | null

const RECAPTURE_REASONS = [
  'Poor lighting — retake in better light',
  'Face partially visible — ensure full face is in frame',
  'Blurry image — hold device steady and retake',
  'Incorrect document captured — recapture the correct document',
  'Face too close to edge — centre the face in frame',
  'Photo taken from screen or printed image — retake in person',
  'Other',
]

/** Suggestion for cases from the earlier screening flow (no document-verification
 * record): from the stored risk result only, worded as next steps. */
function suggestFromRisk(v: VerificationRecordResponse | null | undefined): ActionSuggestion | null {
  const risk = v?.risk
  if (!risk) return null
  const top = risk.top_reason ? humanizeReason(risk.top_reason) : ''
  if (risk.level === 'LOW_RISK') return {
    action: 'CLEAR', title: 'Clear suggested', why: ['Low risk indicator', ...(top ? [top] : [])],
    reason: 'Reviewed: no inconsistency found in the recorded checks.', recapture: [],
  }
  return {
    action: 'HOLD_REFER', title: 'Manual review suggested',
    why: [risk.level === 'HIGH_RISK' ? 'High risk indicator' : 'Medium risk indicator', ...(top ? [top] : [])],
    reason: `Referred for manual verification${top ? `: ${top}` : ''}. Compare the document and the traveller in person before deciding.`,
    recapture: [],
  }
}

const SUGGESTION_BUTTON: Record<string, string> = {
  CLEAR: 'Use suggestion — Clear',
  SECONDARY_REVIEW: 'Use suggestion — Re-capture',
  HOLD_REFER: 'Use suggestion — Manual review',
}

function AdminDecisionPanel({ caseId, onDecisionRecorded, suggestion }: {
  caseId: string; onDecisionRecorded: () => void; suggestion?: ActionSuggestion | null
}) {
  const [action, setAction] = useState<AdminAction>(null)
  const [reason, setReason] = useState('')
  const [selectedReasons, setSelectedReasons] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function applySuggestion(sg: ActionSuggestion) {
    setError(null)
    setAction(sg.action)
    if (sg.action === 'SECONDARY_REVIEW') {
      const picks = sg.recapture.filter((r) => RECAPTURE_REASONS.includes(r))
      setSelectedReasons(picks)
      setReason(picks.length ? '' : sg.reason)
    } else {
      setReason(sg.reason)
    }
  }

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
      <p className="text-xs text-muted-foreground">Confirm that you have reviewed all evidence and the identity is verified.</p>
      <textarea className="w-full rounded-md border border-border bg-background p-2 text-xs focus:border-ring focus:outline-none" rows={2}
        placeholder="Optional reviewer note…" value={reason} onChange={(e) => setReason(e.target.value)} />
      {error && <p className="text-xs text-status-high">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => submit('CLEAR', reason)} disabled={saving}
          className="flex-1 rounded-md bg-status-clear px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {saving ? 'Saving…' : 'Confirm — Verify Identity'}
        </button>
        <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary">Cancel</button>
      </div>
    </div>
  )

  if (action === 'SECONDARY_REVIEW') {
    const finalReason = [...selectedReasons, ...(reason ? [reason] : [])].join('; ')
    return (
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">Select the reason(s) why a new photo or document is needed:</p>
        <div className="space-y-1">
          {RECAPTURE_REASONS.map((r) => (
            <label key={r} className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={selectedReasons.includes(r)} className="accent-accent"
                onChange={(e) => setSelectedReasons((prev) => e.target.checked ? [...prev, r] : prev.filter((x) => x !== r))} />
              {r}
            </label>
          ))}
        </div>
        <textarea className="w-full rounded-md border border-border bg-background p-2 text-xs focus:border-ring focus:outline-none"
          rows={2} placeholder="Additional details…" value={reason} onChange={(e) => setReason(e.target.value)} />
        {error && <p className="text-xs text-status-high">{error}</p>}
        <div className="flex gap-2">
          <button onClick={() => submit('SECONDARY_REVIEW', finalReason)}
            disabled={saving || (selectedReasons.length === 0 && !reason.trim())}
            className="flex-1 rounded-md bg-status-review px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50">
            {saving ? 'Saving…' : 'Request Re-capture'}
          </button>
          <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary">Cancel</button>
        </div>
      </div>
    )
  }

  if (action === 'HOLD_REFER') return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Refer for manual verification. Provide a reason — this is permanently recorded.</p>
      <textarea className="w-full rounded-md border border-border bg-background p-2 text-xs focus:border-ring focus:outline-none"
        rows={3} placeholder="Reason for manual verification referral…" value={reason} onChange={(e) => setReason(e.target.value)} />
      {error && <p className="text-xs text-status-high">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => submit('HOLD_REFER', reason)} disabled={saving || !reason.trim()}
          className="flex-1 rounded-md bg-status-high px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {saving ? 'Saving…' : 'Refer for Manual Verification'}
        </button>
        <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary">Cancel</button>
      </div>
    </div>
  )

  if (action === 'ESCALATE') return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Escalate this case to senior authority. Provide a reason — this is permanently recorded.</p>
      <textarea className="w-full rounded-md border border-border bg-background p-2 text-xs focus:border-ring focus:outline-none"
        rows={3} placeholder="Reason for escalation…" value={reason} onChange={(e) => setReason(e.target.value)} />
      {error && <p className="text-xs text-status-high">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => submit('HOLD_REFER', `ESCALATED: ${reason}`)} disabled={saving || !reason.trim()}
          className="flex-1 rounded-md bg-foreground px-3 py-1.5 text-xs font-semibold text-background hover:opacity-90 disabled:opacity-50">
          {saving ? 'Saving…' : 'Escalate Case'}
        </button>
        <button onClick={() => setAction(null)} className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary">Cancel</button>
      </div>
    </div>
  )

  return (
    <div className="space-y-3">
    {suggestion && (
      <div className={`rounded-md border p-3 ${suggestion.action === 'CLEAR' ? 'border-status-clear/40 bg-status-clear-bg'
        : suggestion.action === 'SECONDARY_REVIEW' ? 'border-status-review/40 bg-status-review-bg' : 'border-status-high/40 bg-status-high-bg'}`}>
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Automatic suggestion</p>
        <p className="mt-0.5 text-sm font-semibold text-foreground">{suggestion.title}</p>
        <ul className="mt-1.5 space-y-1">
          {suggestion.why.slice(0, 5).map((w, i) => (
            <li key={i} className="flex gap-1.5 text-[11px] text-foreground/90"><span aria-hidden>•</span><span>{w}</span></li>
          ))}
        </ul>
        <button onClick={() => applySuggestion(suggestion)}
          className="mt-2 w-full rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent/90">
          {SUGGESTION_BUTTON[suggestion.action]}
        </button>
        <p className="mt-1.5 text-[10px] text-muted-foreground">Generated from the checks. Nothing is recorded until you confirm; edit the reason as needed.</p>
      </div>
    )}
    <div className="grid grid-cols-2 gap-2">
      <button onClick={() => { setAction('CLEAR'); setReason(''); setError(null) }}
        className="flex items-center justify-center gap-1.5 rounded-md border border-status-clear/40 bg-status-clear-bg px-2 py-2 text-xs font-medium text-status-clear hover:bg-status-clear/10">
        <span className="font-bold">✓</span> Clear Case
      </button>
      <button onClick={() => { setAction('SECONDARY_REVIEW'); setReason(''); setSelectedReasons([]); setError(null) }}
        className="flex items-center justify-center gap-1.5 rounded-md border border-status-review/40 bg-status-review-bg px-2 py-2 text-xs font-medium text-status-review hover:bg-status-review/10">
        <span>↺</span> Re-capture
      </button>
      <button onClick={() => { setAction('HOLD_REFER'); setReason(''); setError(null) }}
        className="flex items-center justify-center gap-1.5 rounded-md border border-status-high/40 bg-status-high-bg px-2 py-2 text-xs font-medium text-status-high hover:bg-status-high/10">
        <span>⚑</span> Manual Review
      </button>
      <button onClick={() => { setAction('ESCALATE'); setReason(''); setError(null) }}
        className="flex items-center justify-center gap-1.5 rounded-md border border-border bg-secondary px-2 py-2 text-xs font-medium text-foreground hover:bg-secondary/80">
        <span>↑</span> Escalate
      </button>
    </div>
    </div>
  )
}

// ── OCR field display ────────────────────────────────────────────────────

const OCR_FIELD_LABELS: Record<string, string> = {
  name: 'Full Name', full_name: 'Full Name', owner_name: 'Owner Name',
  passport_number: 'Passport No.', document_number: 'Document No.',
  dl_number: 'Licence No.', visa_number: 'Visa No.', permit_number: 'Permit No.',
  nin_number: 'NIN', cid_number: 'CID', voter_id: 'Voter ID', aadhaar_number: 'Aadhaar',
  nationality: 'Nationality', date_of_birth: 'Date of Birth',
  date_of_issue: 'Date of Issue', date_of_expiry: 'Date of Expiry',
  gender: 'Gender', sex: 'Gender',
  place_of_birth: 'Place of Birth', place_of_issue: 'Place of Issue',
  issuing_authority: 'Issuing Authority',
  fathers_name: "Father's Name", father_name: "Father's Name",
  mothers_name: "Mother's Name",
  blood_group: 'Blood Group', vehicle_classes: 'Vehicle Classes',
  category: 'Category', citizenship_number: 'Citizenship No.',
  permit_type: 'Permit Type', purpose: 'Purpose',
  place_of_visit: 'Place of Visit', registration_no: 'Registration No.',
  address: 'Address', surname: 'Surname', given_name: 'Given Name',
  ref_number: 'Reference No.',
}

// ── Main component ───────────────────────────────────────────────────────────

export function CaseReview() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isReviewer = user?.role === 'REVIEWER'

  const [tab, setTab] = useState<Tab>('overview')
  const [noteText, setNoteText] = useState('')
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  // Cases from Verify document carry a full document verification; the older
  // screening summary blocks below would only repeat it less precisely.
  const [docVerify, setDocVerify] = useState<VerificationOutcome | null>(null)
  const hasDocVerify = docVerify != null

  const caseQuery = useAsync(() => getCase(caseId!), [caseId])
  const identityHistory = useAsync(() => getCaseIdentityHistory(caseId!), [caseId])
  const timeline = useAsync(() => getCaseTimeline(caseId!), [caseId])

  const [noteLoading, setNoteLoading] = useState(false)
  const [noteError, setNoteError] = useState('')

  async function handleAddNote() {
    if (!noteText.trim()) return
    setNoteLoading(true)
    setNoteError('')
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        await addCaseNote(caseId!, noteText)
        setNoteText('')
        setNoteLoading(false)
        caseQuery.refetch()
        return
      } catch (e: unknown) {
        const axErr = e as { response?: { data?: { detail?: string }; status?: number }; message?: string }
        const status = axErr.response?.status
        if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
          setNoteError(axErr.response?.data?.detail ?? 'Could not add note.')
          setNoteLoading(false)
          return
        }
        if (attempt < 2) {
          await new Promise((r) => setTimeout(r, (attempt + 1) * 2000))
          continue
        }
        const msg = axErr.response?.data?.detail ?? axErr.message ?? ''
        setNoteError(msg.includes('Network') || msg.includes('timeout')
          ? 'Backend is waking up — wait a moment and try again.'
          : `Could not add note: ${msg || 'Unknown error'}`)
      }
    }
    setNoteLoading(false)
  }

  if (caseQuery.loading) return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent" />
      <p className="text-sm">Loading case…</p>
    </div>
  )
  if (caseQuery.error) return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <span className="text-4xl">⚠</span>
      <p className="text-sm text-status-high">{caseQuery.error}</p>
      <p className="text-xs text-muted-foreground max-w-sm text-center">
        This may happen if the server is waking up after inactivity. Please try again.
      </p>
      <div className="flex gap-2">
        <button onClick={() => caseQuery.refetch()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90">
          Retry
        </button>
        <button onClick={() => navigate(-1)}
          className="rounded-md border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-secondary">
          Go Back
        </button>
      </div>
    </div>
  )
  const c = caseQuery.data
  if (!c) return null

  const v = c.verification
  const findings = v ? buildFindings(v) : []
  const awaitingDecision = c.status === 'SENT' || c.status === 'REVIEW_REQUIRED'

  const ocr = v?.ocr?.fields ?? {}
  const docNumber = ocr.passport_number ?? ocr.dl_number ?? ocr.license_number ?? ocr.document_number ?? ocr.visa_number ?? ocr.permit_number ?? ocr.nin_number ?? ocr.cid_number ?? null
  const displayName = c.traveler_name ?? ocr.full_name ?? ocr.name ?? ocr.owner_name ?? null
  const displayDocType = DOC_TYPE_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type
  const displayGender = ocr.sex ?? ocr.gender ?? null

  const issues = findings.filter((f) => f.tone === 'alert' || f.tone === 'review')
  const topIssues = issues.slice(0, 4)

  const riskLabel = v?.risk.level === 'HIGH_RISK' ? 'High Risk'
    : v?.risk.level === 'MEDIUM_RISK' ? 'Medium Risk' : 'Low Risk'
  const riskColor = v?.risk.level === 'HIGH_RISK' ? 'status-high'
    : v?.risk.level === 'MEDIUM_RISK' ? 'status-review' : 'status-clear'

  // Waiting time
  const waitingMs = c.sent_at ? Date.now() - new Date(c.sent_at).getTime() : Date.now() - new Date(c.created_at).getTime()
  const waitingHours = Math.floor(waitingMs / 3600000)
  const waitingMins = Math.floor((waitingMs % 3600000) / 60000)
  const waitingLabel = waitingHours > 0 ? `${waitingHours}h ${waitingMins}m` : `${waitingMins}m`
  const isOverdue = waitingHours >= 24

  return (
    <div className="space-y-3">
      {/* ══════════════════════════════════════════════════════════════════
         TOP BAR — case number, status, priority, risk in one compact row
         ══════════════════════════════════════════════════════════════════ */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-xs text-accent hover:underline shrink-0">← Back</button>
          <div className="h-4 w-px bg-border" />
          <span className="text-sm font-semibold text-foreground">{c.case_number}</span>
          <StatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
        </div>
        <div className="flex items-center gap-3">
          {v && (
            <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold
              bg-${riskColor}-bg text-${riskColor} border-${riskColor}/30`}>
              {v.risk.level === 'HIGH_RISK' ? '⚑' : v.risk.level === 'MEDIUM_RISK' ? '⚠' : '✓'} {riskLabel}
            </span>
          )}
          <span className={`text-xs ${isOverdue ? 'text-status-high font-semibold' : 'text-muted-foreground'}`}>
            {isOverdue ? '⚠ ' : ''}Waiting: {waitingLabel}
          </span>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
         TWO-COLUMN LAYOUT
         ══════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">

        {/* ── LEFT: Tabbed workspace (3/5 = 60%) ── */}
        <div className="space-y-3 lg:col-span-3">
          {/* Tab bar */}
          <div className="flex gap-0.5 border-b border-border overflow-x-auto">
            {(['overview', 'evidence', 'risk', 'timeline', 'history'] as const).map((key) => {
              const labels: Record<Tab, string> = {
                overview:  'Overview',
                evidence:  'Evidence',
                risk:      'Risk Analysis',
                timeline:  'Timeline',
                history:   'History',
              }
              const hasIssue = key === 'risk' && issues.length > 0
              return (
                <button key={key} onClick={() => setTab(key)}
                  className={`relative px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
                    tab === key
                      ? 'border-b-2 border-accent text-accent'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}>
                  {labels[key]}
                  {hasIssue && (
                    <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-status-high" />
                  )}
                </button>
              )
            })}
          </div>

          {/* ── OVERVIEW TAB ── */}
          {tab === 'overview' && (
            <div className="space-y-4">
              <DocVerifyCasePanel caseId={c.id} onLoaded={setDocVerify} />
              {/* Risk summary banner */}
              {v && !hasDocVerify && (
                <div className={`rounded-lg border px-4 py-3 ${
                  v.risk.level === 'HIGH_RISK'
                    ? 'border-status-high/50 bg-status-high-bg'
                    : v.risk.level === 'MEDIUM_RISK'
                      ? 'border-status-review/50 bg-status-review-bg'
                      : 'border-status-clear/50 bg-status-clear-bg'
                }`}>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold text-${riskColor}`}>
                      {v.risk.level === 'HIGH_RISK' ? '⚑' : v.risk.level === 'MEDIUM_RISK' ? '⚠' : '✓'}
                    </span>
                    <div>
                      <p className={`text-sm font-semibold text-${riskColor}`}>
                        {v.risk.level === 'HIGH_RISK' ? 'Immediate Review Required'
                          : v.risk.level === 'MEDIUM_RISK' ? 'Review Recommended'
                          : 'All Checks Passed'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {humanizeReason(v.risk.top_reason)}
                      </p>
                    </div>
                  </div>
                  {topIssues.length > 0 && (
                    <div className="mt-3 space-y-1.5">
                      <p className="text-xs font-semibold text-foreground uppercase tracking-wide">Why this needs attention</p>
                      {topIssues.map((f) => (
                        <div key={f.label} className="flex items-start gap-2">
                          <span className={`mt-0.5 text-xs ${f.tone === 'alert' ? 'text-status-high' : 'text-status-review'}`}>
                            {f.tone === 'alert' ? '✕' : '⚠'}
                          </span>
                          <div>
                            <span className="text-xs font-medium text-foreground">{f.label}:</span>{' '}
                            <span className="text-xs text-muted-foreground">{f.summary}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Key findings — only non-clear ones */}
              {findings.length > 0 && !hasDocVerify && (
                <Card title="Key Findings">
                  <div className="divide-y divide-border">
                    {findings.filter((f) => f.tone !== 'none').slice(0, 6).map((f) => (
                      <FindingRow key={f.label} f={f} />
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ── EVIDENCE TAB ── */}
          {tab === 'evidence' && (
            <div className="space-y-4">
              {v ? (
                <EvidenceImages verificationId={v.id} caseCreatedAt={c.created_at} />
              ) : (
                <Card><p className="text-sm text-muted-foreground">No document or photo captured for this case.</p></Card>
              )}

              {/* OCR extracted fields (earlier screening flow; Verify-document cases show them in the panel) */}
              {!hasDocVerify && Object.keys(ocr).length > 0 && (
                <Card title="Extracted Document Fields">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0">
                    {Object.entries(ocr).map(([key, value]) => {
                      if (!value || key.startsWith('mrz_')) return null
                      const label = OCR_FIELD_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                      return (
                        <div key={key} className="flex items-baseline justify-between border-b border-border/40 py-1.5">
                          <span className="text-xs text-muted-foreground">{label}</span>
                          <span className="text-xs font-medium text-foreground text-right max-w-[60%] truncate">
                            {value}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                  {/* MRZ section */}
                  {(ocr.mrz_line1 || ocr.mrz_line2) && (
                    <div className="mt-4 pt-3 border-t border-border">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Machine-Readable Zone</p>
                      <div className="rounded-md bg-background border border-border p-3 font-mono text-xs text-accent leading-relaxed">
                        {ocr.mrz_line1 && <div>{ocr.mrz_line1}</div>}
                        {ocr.mrz_line2 && <div>{ocr.mrz_line2}</div>}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {/* Verification findings */}
              {v && findings.length > 0 && (
                <Card title="Verification Checks">
                  <div className="divide-y divide-border">
                    {findings.map((f) => <FindingRow key={f.label} f={f} />)}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ── RISK ANALYSIS TAB ── */}
          {tab === 'risk' && (
            <div className="space-y-4">
              {v ? (
                <>
                  {/* Overall status */}
                  <div className={`rounded-lg border px-4 py-3 ${
                    v.risk.level === 'HIGH_RISK'
                      ? 'border-status-high/50 bg-status-high-bg'
                      : v.risk.level === 'MEDIUM_RISK'
                        ? 'border-status-review/50 bg-status-review-bg'
                        : 'border-status-clear/50 bg-status-clear-bg'
                  }`}>
                    <div className="flex items-center gap-2">
                      <span className={`text-lg font-bold text-${riskColor}`}>
                        {v.risk.level === 'HIGH_RISK' ? '⚑' : v.risk.level === 'MEDIUM_RISK' ? '⚠' : '✓'}
                      </span>
                      <p className={`text-sm font-semibold text-${riskColor}`}>
                        {v.risk.level === 'HIGH_RISK' ? 'Immediate Review Required'
                          : v.risk.level === 'MEDIUM_RISK' ? 'Review Recommended'
                          : 'All Checks Passed'}
                      </p>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{humanizeReason(v.risk.top_reason)}</p>
                  </div>

                  {/* Grouped findings by category */}
                  {(() => {
                    const docFindings = findings.filter((f) => f.category === 'document')
                    const idFindings = findings.filter((f) => f.category === 'identity')
                    const secFindings = findings.filter((f) => f.category === 'security')
                    const groups: { title: string; icon: string; items: FindingCard[] }[] = [
                      { title: 'Document Issues', icon: '📄', items: docFindings },
                      { title: 'Identity Concerns', icon: '👤', items: idFindings },
                      { title: 'Security Alerts', icon: '🛡', items: secFindings },
                    ]
                    return groups.filter((g) => g.items.length > 0).map((g) => (
                      <Card key={g.title}>
                        <div className="flex items-center gap-2 mb-2">
                          <span>{g.icon}</span>
                          <h3 className="text-sm font-semibold text-foreground">{g.title}</h3>
                          {g.items.some((f) => f.tone === 'alert') && (
                            <span className="text-[10px] bg-status-high-bg text-status-high px-1.5 py-0.5 rounded-full font-medium">
                              Action needed
                            </span>
                          )}
                        </div>
                        <div className="divide-y divide-border">
                          {g.items.map((f) => <FindingRow key={f.label} f={f} />)}
                        </div>
                      </Card>
                    ))
                  })()}

                  {/* Diagnostics */}
                  <div className="border-t border-border pt-3">
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
                </>
              ) : (
                <Card><p className="text-sm text-muted-foreground">No verification data available for this case.</p></Card>
              )}
            </div>
          )}

          {/* ── TIMELINE TAB ── */}
          {tab === 'timeline' && (
            <Card title="Case Timeline">
              {timeline.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {timeline.data && timeline.data.length === 0 && (
                <p className="text-sm text-muted-foreground">No events recorded for this case yet.</p>
              )}
              {timeline.data && timeline.data.length > 0 && (
                <ol className="space-y-0 border-l-2 border-border pl-4">
                  {timeline.data.map((event, i) => {
                    const label = TIMELINE_LABELS[event.event_type] ?? event.action
                    const isDecision = event.event_type?.includes('DECISION')
                    const isClear = event.event_type?.includes('CLEAR')
                    const isHold = event.event_type?.includes('HOLD') || event.event_type?.includes('FLAG')
                    const isReview = event.event_type?.includes('REVIEW') || event.event_type?.includes('SENT')
                    const dotColor = isClear ? 'bg-status-clear border-status-clear/50'
                      : isHold ? 'bg-status-high border-status-high/50'
                      : isReview ? 'bg-status-review border-status-review/50'
                      : 'bg-accent border-accent/50'
                    const icon = isClear ? '✓' : isHold ? '⚑' : isReview ? '➤'
                      : event.event_type === 'CREATED' ? '◉'
                      : event.event_type === 'VIEWED' ? '👁'
                      : event.event_type === 'NOTE_ADDED' ? '✎' : '●'
                    return (
                      <li key={i} className="relative pb-5 last:pb-0">
                        <div className={`absolute -left-[1.35rem] mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 text-[8px] ${dotColor}`}>
                          <span className="text-white">{isDecision ? '' : ''}</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-sm shrink-0 mt-0">{icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-baseline justify-between gap-2">
                              <p className="text-sm font-medium text-foreground">{label}</p>
                              <p className="text-[10px] text-muted-foreground shrink-0">
                                {new Date(event.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                              </p>
                            </div>
                            {event.actor_username && (
                              <p className="text-xs text-muted-foreground">by {event.actor_username}</p>
                            )}
                            {event.detail && (
                              <p className="mt-1 rounded bg-secondary px-2 py-1 text-xs text-muted-foreground leading-relaxed">
                                {humanizeReason(event.detail)}
                              </p>
                            )}
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ol>
              )}
            </Card>
          )}

          {/* ── HISTORY TAB ── */}
          {tab === 'history' && (
            <div className="space-y-4">
              {/* Identity history */}
              <Card title="Previous Screenings">
                {identityHistory.loading && <p className="text-sm text-muted-foreground">Loading identity history…</p>}
                {identityHistory.data && identityHistory.data.length === 0 && (
                  <div className="py-4 text-center space-y-2">
                    <p className="text-sm font-medium text-foreground">No prior crossing records</p>
                    <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                      No other cases share a similar facial identity with this record. This appears to be a first-time entry.
                    </p>
                  </div>
                )}
                {identityHistory.data && identityHistory.data.length > 0 && (
                  <>
                    <div className="mb-4 rounded-lg border border-status-review/40 bg-status-review-bg px-4 py-2.5 text-sm text-status-review">
                      <p className="font-semibold">⚠ {identityHistory.data.length} prior crossing record(s) found</p>
                      <p className="mt-0.5 text-xs">
                        These cases share similar facial characteristics. Review each entry to confirm consistent identity.
                      </p>
                    </div>
                    <ol className="relative border-l-2 border-border space-y-0">
                      {[...identityHistory.data]
                        .sort((a, b) => new Date(b.occurred_at ?? 0).getTime() - new Date(a.occurred_at ?? 0).getTime())
                        .map((r, i) => {
                          const isStrong = (r.similarity ?? 0) >= 0.75
                          return (
                            <li key={r.record_id ?? i} className="ml-4 pb-5">
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
                                  <div><span className="text-muted-foreground">Name: </span><span className="font-medium text-foreground">{r.declared_name}</span></div>
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

              {/* Decision history */}
              {c.decisions.length > 0 && (
                <Card title="Previous Decisions">
                  <ul className="space-y-2">
                    {c.decisions.map((d, i) => {
                      const isClearD = d.decision === 'CLEAR'
                      const isHoldD = d.decision === 'HOLD_REFER'
                      const icon = isClearD ? '✓' : isHoldD ? '⚑' : '⚠'
                      const accentClass = isClearD ? 'text-status-clear' : isHoldD ? 'text-status-high' : 'text-status-review'
                      const bgClass = isClearD ? 'bg-status-clear/5 border-status-clear/20' : isHoldD ? 'bg-status-high/5 border-status-high/20' : 'bg-status-review/5 border-status-review/20'
                      return (
                        <li key={i} className={`rounded-lg border p-3 ${bgClass}`}>
                          <div className="flex items-center gap-2">
                            <span className={`text-base ${accentClass}`}>{icon}</span>
                            <p className={`text-sm font-semibold ${accentClass}`}>
                              {DECISION_LABELS[d.decision] ?? d.decision.replace(/_/g, ' ')}
                            </p>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            by {d.officer_username ?? 'reviewer'} · {new Date(d.created_at).toLocaleString()}
                          </p>
                          {d.reason && (
                            <p className="mt-1.5 rounded bg-secondary px-2 py-1.5 text-xs text-muted-foreground leading-relaxed">
                              {humanizeReason(d.reason)}
                            </p>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </Card>
              )}

              {/* Network panel */}
              <div className="space-y-2">
                <Card>
                  <p className="mb-1 text-sm font-medium text-foreground">Identity & Travel Connections</p>
                  <p className="text-xs text-muted-foreground">
                    Relationships between people, documents, checkpoints, and travel events.
                    A connection here is an observation — not an accusation.
                  </p>
                </Card>
                <CaseNetworkPanel caseId={c.id} />
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Sticky sidebar (2/5 = 40%) ── */}
        <div className="lg:col-span-2 space-y-3 lg:sticky lg:top-20 lg:self-start">
          {/* Identity card */}
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">Identity</p>
            <h2 className="text-lg font-bold text-foreground leading-tight">{displayName ?? 'Name not extracted'}</h2>
            <div className="mt-3 space-y-1.5">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Document</span>
                <span className="font-medium text-foreground">{displayDocType}</span>
              </div>
              {docNumber && (
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">Number</span>
                  <span className="font-medium text-foreground font-mono">{maskDocNumber(docNumber)}</span>
                </div>
              )}
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Nationality</span>
                <span className="font-medium text-foreground">{c.nationality || ocr.nationality || '—'}</span>
              </div>
              {displayGender && /^(m|f|male|female|other|transgender)$/i.test(displayGender.trim()) && (
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">Gender</span>
                  <span className="font-medium text-foreground">
                    {displayGender.trim().charAt(0).toUpperCase() === 'M' ? 'Male' : displayGender.trim().charAt(0).toUpperCase() === 'F' ? 'Female' : displayGender.trim()}
                  </span>
                </div>
              )}
              {ocr.date_of_birth && (
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">DOB</span>
                  <span className="font-medium text-foreground">{ocr.date_of_birth}</span>
                </div>
              )}
              <div className="border-t border-border/50 my-1.5" />
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Checkpoint</span>
                <span className="font-medium text-foreground">{c.checkpoint_code}</span>
              </div>
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Officer</span>
                <span className="font-medium text-foreground">{c.field_officer_username}</span>
              </div>
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Screened</span>
                <span className="font-medium text-foreground">
                  {new Date(c.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          </div>

          {/* Decision panel */}
          {isReviewer && awaitingDecision && (
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs font-semibold text-foreground uppercase tracking-wide mb-2">Take Action</p>
              <p className="text-[10px] text-muted-foreground mb-3">
                Review all evidence before recording your decision. Every action is permanently logged.
              </p>
              <AdminDecisionPanel caseId={c.id} onDecisionRecorded={() => caseQuery.refetch()}
                suggestion={docVerify ? suggestAction(docVerify) : suggestFromRisk(v)} />
            </div>
          )}

          {!isReviewer && c.status === 'PENDING' && (
            <Card title="Submit for Review">
              <p className="mb-2 text-xs text-muted-foreground">
                Forward this case to the admin review queue.
              </p>
              <button
                onClick={async () => { await submitCase(c.id); caseQuery.refetch() }}
                className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
                Submit for Review
              </button>
            </Card>
          )}

          {/* Notes */}
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs font-semibold text-foreground uppercase tracking-wide mb-2">Notes</p>
            <ul className="mb-3 space-y-2 max-h-48 overflow-y-auto">
              {c.notes.map((n) => (
                <li key={n.id} className="border-b border-border/40 pb-2 last:border-0">
                  <p className="text-[10px] text-muted-foreground">
                    {n.author_username} · {new Date(n.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </p>
                  <p className="mt-0.5 whitespace-pre-line text-xs text-foreground">{n.note}</p>
                </li>
              ))}
              {c.notes.length === 0 && <p className="text-xs text-muted-foreground">No notes yet.</p>}
            </ul>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground">Add a note</span>
              <button
                onClick={() => {
                  const risk = v?.risk
                  const checkpoint = c.checkpoint_code ?? 'this checkpoint'
                  const docType = DOC_TYPE_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type ?? 'document'
                  const nat = c.nationality ?? ''
                  const riskLevel = risk?.level === 'HIGH_RISK' ? 'High risk' : risk?.level === 'MEDIUM_RISK' ? 'Medium risk' : 'Low risk'
                  let reason = humanizeReason(risk?.top_reason ?? '')
                  if (reason.length > 120) reason = reason.slice(0, 120) + '…'
                  const actionMap: Record<string, string> = {
                    HIGH_RISK: 'Possible inconsistency detected — refer for manual verification and compare the traveller in person.',
                    MEDIUM_RISK: 'Review required — confirm the flagged details against the document before deciding.',
                    LOW_RISK: 'No inconsistency found in the recorded checks.',
                  }
                  const actionText = actionMap[risk?.level ?? ''] ?? 'Further review recommended.'
                  setNoteText(`Document reviewed at ${checkpoint}. ${riskLevel} — ${docType}${nat ? ` (${nat})` : ''}. ${reason ? reason + '. ' : ''}${actionText}`)
                }}
                className="text-[10px] text-accent hover:text-accent/80 border border-accent/30 px-1.5 py-0.5 rounded hover:bg-accent/10 transition-colors"
              >
                Generate
              </button>
            </div>
            <textarea
              className="w-full rounded-md border border-border bg-background p-2 text-xs focus:border-ring focus:outline-none"
              rows={2} placeholder="Add a note…" value={noteText}
              onChange={(e) => setNoteText(e.target.value)} />
            {noteError && <p className="mt-1 text-[10px] text-status-high">{noteError}</p>}
            <button onClick={handleAddNote} disabled={noteLoading || !noteText.trim()}
              className="mt-1.5 w-full rounded-md border border-border py-1.5 text-xs font-medium text-foreground hover:bg-secondary disabled:opacity-50">
              {noteLoading ? 'Saving…' : 'Add Note'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
