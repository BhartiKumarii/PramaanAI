import type { CheckResult, VerificationOutcome } from '../api/docverify'

/**
 * Automatic suggestion for the admin's "Take action" panel, written from the
 * document-verification checks behind a case. It only pre-fills the form —
 * the admin reads the evidence and confirms. Wording never accuses: it names
 * the check and what to do next, never "fake", "fraud" or "deny entry".
 */
export type SuggestedAction = 'CLEAR' | 'SECONDARY_REVIEW' | 'HOLD_REFER'

export interface ActionSuggestion {
  action: SuggestedAction
  title: string
  why: string[]
  reason: string
  /** For SECONDARY_REVIEW: re-capture reasons to pre-tick (must match RECAPTURE_REASONS). */
  recapture: string[]
}

// Checks that describe how the photo was taken — fixed by a better capture.
const CAPTURE_CHECKS = new Set([
  'image_quality', 'document_framing', 'document_detected', 'document_proportions',
  'document_face_quality', 'ocr_confidence', 'ocr',
])

function isCaptureIssue(c: CheckResult): boolean {
  const flags = (c.details?.flags as string[] | undefined) ?? []
  return CAPTURE_CHECKS.has(c.name) || flags.includes('retake_live_capture')
}

const RECAPTURE: Record<string, string> = {
  blur: 'Blurry image — hold device steady and retake',
  light: 'Poor lighting — retake in better light',
  face: 'Face partially visible — ensure full face is in frame',
  edge: 'Face too close to edge — centre the face in frame',
  screen: 'Photo taken from screen or printed image — retake in person',
  document: 'Incorrect document captured — recapture the correct document',
}

function issues(r: VerificationOutcome): CheckResult[] {
  return r.check_details.filter((c) => c.status !== 'PASS' && c.status !== 'NOT_APPLICABLE')
}

function recaptureReasons(checks: CheckResult[]): string[] {
  const out = new Set<string>()
  for (const c of checks) {
    const s = c.summary.toLowerCase()
    if (/blur|sharp|focus/.test(s)) out.add(RECAPTURE.blur)
    if (/light|glare|dark|exposure/.test(s)) out.add(RECAPTURE.light)
    if (/cut off|edge|cropped/.test(s)) out.add(c.name.includes('face') || c.name === 'liveness' ? RECAPTURE.edge : RECAPTURE.document)
    if (/no clear face|no face|face not found/.test(s)) out.add(RECAPTURE.face)
    if (c.name === 'liveness' && /photo or screen|gallery/.test(s)) out.add(RECAPTURE.screen)
    if (c.name === 'document_type' && c.status !== 'PASS') out.add(RECAPTURE.document)
    if ((c.name === 'ocr' || c.name === 'ocr_confidence') && out.size === 0) out.add(RECAPTURE.blur)
  }
  return [...out]
}

export function suggestAction(r: VerificationOutcome): ActionSuggestion {
  const open = issues(r)
  const blocking = open.filter((c) => c.blocking)
  const strong = blocking.filter((c) => (c.status === 'FAIL' || c.strong_evidence) && !isCaptureIssue(c))
  const face = r.check_details.find((c) => c.name === 'face_verification')
  const liveness = r.check_details.find((c) => c.name === 'liveness')
  const identity = (r.identity?.face_cluster?.status === 'CLUSTER_FOUND' && (r.identity?.face_cluster?.cluster_size ?? 0) > 1)
    // Same document seen before under the same name is a routine repeat crossing, not a finding.
    || r.identity?.duplicate_document?.status === 'DIFFERENT_IDENTITY_REUSE'
  const captureOnly = blocking.length > 0 && blocking.every(isCaptureIssue)
  const faceUnclear = face && face.status === 'NOT_VERIFIED' && /no clear face|not possible/i.test(face.summary)
  const livenessWeak = liveness && liveness.status !== 'PASS'

  const line = (c: CheckResult) => c.summary.replace(/\s+/g, ' ').trim()
  // Advisory liveness result, always shown to the admin when it is not a pass.
  const livenessNote = livenessWeak && liveness ? [`Liveness: ${line(liveness)}`] : []

  // 1. Strong findings or identity links → a person should look at it.
  if (strong.length > 0 || identity) {
    const why = [...strong.map(line), ...livenessNote, ...(identity ? [r.identity?.duplicate_document?.status === 'DIFFERENT_IDENTITY_REUSE'
      ? r.identity.duplicate_document.reason : r.identity?.face_cluster?.reason ?? 'Linked to another identity record'] : [])]
    return {
      action: 'HOLD_REFER',
      title: 'Manual review suggested',
      why,
      reason: `Referred for manual verification. Findings: ${why.join('; ')}. Compare the document and the traveller in person before deciding.`,
      recapture: [],
    }
  }

  // 2. Only capture problems (blur, framing, no clear face, liveness not done) → re-capture.
  if (captureOnly || (blocking.length === 0 && (faceUnclear || livenessWeak))) {
    const src = [...blocking, ...(faceUnclear && face ? [face] : []), ...(livenessWeak && liveness ? [liveness] : [])]
    const picks = recaptureReasons(src)
    return {
      action: 'SECONDARY_REVIEW',
      title: 'Re-capture suggested',
      why: src.map(line),
      reason: src.length ? `New capture needed: ${src.map(line).join('; ')}.` : '',
      recapture: picks,
    }
  }

  // 3. Other checks need attention (dates, MRZ, registry, stamps…) → manual review.
  if (blocking.length > 0) {
    const why = [...blocking.map(line), ...livenessNote]
    return {
      action: 'HOLD_REFER',
      title: 'Manual review suggested',
      why,
      reason: `Referred for manual verification: ${why.join('; ')}. Confirm these details against the document and the traveller.`,
      recapture: [],
    }
  }

  // 4. Nothing open.
  const advisory = open.filter((c) => !c.blocking).map(line)
  return {
    action: 'CLEAR',
    title: 'Clear suggested',
    why: ['All blocking checks passed', ...advisory.map((a) => `Advisory: ${a}`)],
    reason: r.suggested_reasons?.clear ?? 'All blocking checks passed; identity details consistent on review.',
    recapture: [],
  }
}
