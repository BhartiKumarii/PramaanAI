/**
 * Translation layer — converts AI/ML pipeline output to officer-readable language.
 * Technical diagnostics stay behind the "System Diagnostics" collapsible only.
 */

export interface VerificationStatus {
  status: 'VERIFIED' | 'MANUAL_CHECK_REQUIRED' | 'VERIFICATION_FAILED' | 'RETAKE_REQUIRED'
  label: string
  explanation: string
  recommendation: string[]
}

export interface CheckResult {
  label: string
  status: 'PASS' | 'REVIEW' | 'FAIL'
  explanation: string
  action: string
  icon: '✓' | '⚠' | '✗'
  technical?: string
}

export function translateVerificationSignals(verification: any): CheckResult[] {
  const checks: CheckResult[] = []

  // Document readability
  if (verification.ocr) {
    const confidence = Math.round(verification.ocr.ocr_confidence * 100)
    checks.push({
      label: 'Document information',
      status: confidence >= 70 ? 'PASS' : confidence >= 40 ? 'REVIEW' : 'FAIL',
      explanation:
        confidence >= 70
          ? 'Document details were read successfully.'
          : confidence >= 40
            ? 'Some details could not be read clearly.'
            : 'Document details could not be read reliably.',
      action:
        confidence >= 70
          ? 'No action required.'
          : 'Ask the traveler to present the document again in better light. Retake the scan.',
      icon: confidence >= 70 ? '✓' : confidence >= 40 ? '⚠' : '✗',
      technical: `OCR confidence: ${confidence}%`,
    })
  }

  // Document format / MRZ
  if (verification.validation) {
    const failedChecks = verification.validation.findings?.filter((f: any) => f.status === 'FAIL') ?? []
    const expiredCheck = failedChecks.find((f: any) => f.check === 'expiry')
    const mrzFailed = failedChecks.some((f: any) => f.check?.includes('mrz') || f.check?.includes('checksum'))

    if (expiredCheck) {
      checks.push({
        label: 'Document validity',
        status: 'FAIL',
        explanation: humaniseExpiryReason(expiredCheck.reason),
        action: 'Do not accept this document. Ask the traveler if they have a valid document. Refer to supervisor.',
        icon: '✗',
        technical: `Expiry check: ${expiredCheck.reason}`,
      })
    } else if (mrzFailed) {
      checks.push({
        label: 'Document integrity',
        status: 'FAIL',
        explanation: 'The machine-readable zone on this document contains an error. The document may have been altered or is not genuine.',
        action: 'Examine the document physically. Compare machine-readable text with the printed fields. Refer to supervisor.',
        icon: '✗',
        technical: `MRZ validation: FAIL — ${failedChecks.map((f: any) => f.check).join(', ')}`,
      })
    } else {
      checks.push({
        label: 'Document integrity',
        status: verification.validation.status === 'PASS' ? 'PASS' : 'REVIEW',
        explanation:
          verification.validation.status === 'PASS'
            ? 'Document format and data checks passed.'
            : 'Some document checks require review.',
        action:
          verification.validation.status === 'PASS'
            ? 'No action required.'
            : 'Review the document carefully. Compare all printed fields against the machine-readable zone.',
        icon: verification.validation.status === 'PASS' ? '✓' : '⚠',
        technical: `Validation: ${verification.validation.status}`,
      })
    }
  }

  // Document appearance / forensics
  if (verification.tampering) {
    const riskPercent = Math.round(verification.tampering.tampering_risk * 100)
    const finding = verification.tampering.findings?.[0]
    checks.push({
      label: 'Document appearance',
      status: riskPercent <= 25 ? 'PASS' : riskPercent <= 55 ? 'REVIEW' : 'FAIL',
      explanation:
        riskPercent <= 25
          ? 'No signs of alteration detected.'
          : riskPercent <= 55
            ? humaniseTamperingReason(finding?.reason ?? '')
            : humaniseTamperingReason(finding?.reason ?? ''),
      action:
        riskPercent <= 25
          ? 'No action required.'
          : riskPercent <= 55
            ? 'Examine the document in person. Look for signs of printing over existing text, uneven ink, or mismatched fonts.'
            : 'Do not accept this document without further investigation. Examine physically and refer to supervisor.',
      icon: riskPercent <= 25 ? '✓' : riskPercent <= 55 ? '⚠' : '✗',
      technical: `ELA tampering risk: ${riskPercent}%`,
    })
  }

  // Face comparison
  if (verification.face) {
    const sim = verification.face.similarity ?? 0
    const match = verification.face.match
    checks.push({
      label: 'Photo comparison',
      status: match ? 'PASS' : sim >= 0.55 ? 'REVIEW' : 'FAIL',
      explanation: match
        ? 'The live photo is consistent with the document photo.'
        : sim >= 0.55
          ? 'The live photo is a partial match with the document photo. Manual comparison recommended.'
          : 'The live photo does not match the document photo.',
      action: match
        ? 'No action required.'
        : sim >= 0.55
          ? 'Compare the person physically with the document photo. If uncertain, retake the photo and compare again.'
          : 'Do not proceed without further review. Retake the live photo and compare again. If mismatch persists, refer to supervisor.',
      icon: match ? '✓' : sim >= 0.55 ? '⚠' : '✗',
      technical: `Face similarity: ${sim.toFixed(3)} (threshold: 0.75)`,
    })
  }

  // Liveness
  if (verification.liveness) {
    const st = verification.liveness.status
    checks.push({
      label: 'Live person check',
      status: st === 'LIVE' ? 'PASS' : st === 'SUSPECTED_SPOOF' ? 'FAIL' : 'REVIEW',
      explanation:
        st === 'LIVE'
          ? 'The photo was taken of a live person.'
          : st === 'SUSPECTED_SPOOF'
            ? 'The photo may have been taken from a screen or a printed image — not a live person.'
            : 'The live person check could not be completed reliably.',
      action:
        st === 'LIVE'
          ? 'No action required.'
          : st === 'SUSPECTED_SPOOF'
            ? 'Retake the photo directly of the person. Ensure no screens or printed images are in frame.'
            : 'Retake the live photo under good lighting with the person facing the camera directly.',
      icon: st === 'LIVE' ? '✓' : st === 'SUSPECTED_SPOOF' ? '✗' : '⚠',
      technical: `Liveness status: ${st}`,
    })
  }

  // Photo authenticity
  if (verification.deepfake && verification.deepfake.status === 'ANALYZED') {
    const score = verification.deepfake.score ?? 0
    checks.push({
      label: 'Photo authenticity',
      status: score <= 0.35 ? 'PASS' : score <= 0.7 ? 'REVIEW' : 'FAIL',
      explanation:
        score <= 0.35
          ? 'The photo appears to be authentic.'
          : score <= 0.7
            ? 'The photo has some characteristics that require additional review.'
            : 'The photo contains characteristics that suggest it may not be genuine.',
      action:
        score <= 0.35
          ? 'No action required.'
          : score <= 0.7
            ? 'Retake the photo to obtain a clearer image. If concern remains, refer to supervisor.'
            : 'Request a new live photo. If the issue persists, refer to supervisor for manual review.',
      icon: score <= 0.35 ? '✓' : score <= 0.7 ? '⚠' : '✗',
      technical: `Authenticity score: ${score.toFixed(2)}`,
    })
  }

  // Security records / watchlist
  if (verification.registry) {
    const hit = verification.registry.status === 'HIT'
    const hitDetails = verification.registry.hits?.[0]
    checks.push({
      label: 'Security records check',
      status: hit ? 'FAIL' : 'PASS',
      explanation: hit
        ? `Alert: This document is flagged in our records.${hitDetails ? ` Reason: ${hitDetails.registry_reason}` : ''}`
        : 'No alerts found in security records.',
      action: hit
        ? 'Do not allow entry. Detain the traveler and immediately notify your supervisor. Record the interaction.'
        : 'No action required.',
      icon: hit ? '✗' : '✓',
      technical: `Watchlist lookup: ${verification.registry.status}`,
    })
  }

  // Citizen registry / document database
  if (verification.citizen_registry) {
    const st = verification.citizen_registry.status
    const mismatches = verification.citizen_registry.mismatched_fields ?? []
    checks.push({
      label: 'Identity records match',
      status: st === 'MATCH' ? 'PASS' : st === 'MISMATCH' ? 'FAIL' : 'REVIEW',
      explanation:
        st === 'MATCH'
          ? 'Document details match our identity records.'
          : st === 'MISMATCH'
            ? `Identity mismatch — the document details do not match our records.${mismatches.length > 0 ? ` Fields with discrepancies: ${mismatches.join(', ')}.` : ''}`
            : st === 'NO_RECORD'
              ? 'No matching record found in identity database.'
              : humaniseCitizenRegistryReason(verification.citizen_registry.reason),
      action:
        st === 'MATCH'
          ? 'No action required.'
          : st === 'MISMATCH'
            ? 'Ask the traveler to explain the discrepancy. Compare document physically. Refer to supervisor if unresolved.'
            : "Verify the document manually against the traveler's details. Ask for supporting identification.",
      icon: st === 'MATCH' ? '✓' : st === 'MISMATCH' ? '✗' : '⚠',
      technical: `Registry: ${st} — ${verification.citizen_registry.reason}`,
    })
  }

  // Identity graph / multiple records
  if (verification.identity_graph) {
    const cluster = verification.identity_graph.status === 'CLUSTER_FOUND'
    checks.push({
      label: 'Previous identity records',
      status: cluster ? 'REVIEW' : 'PASS',
      explanation: cluster
        ? `Similar facial identity information was found in ${verification.identity_graph.cluster_size ?? 'multiple'} other record(s) with different details. This may indicate multiple crossings with different documents.`
        : 'No conflicting identity records found.',
      action: cluster
        ? 'Review the related records carefully. Ask the traveler if they have crossed this checkpoint before under a different name or document. Refer to supervisor.'
        : 'No action required.',
      icon: cluster ? '⚠' : '✓',
      technical: `Identity graph: ${verification.identity_graph.status} — cluster size ${verification.identity_graph.cluster_size ?? 1}`,
    })
  }

  return checks
}

// ── Helpers for translating raw backend reason strings ──────────────────────

function humaniseExpiryReason(reason: string): string {
  // "document expiry 2016-04-27 vs today 2026-09-21: expired"
  const m = reason.match(/document expiry (\d{4}-\d{2}-\d{2})/i)
  if (m) {
    const d = new Date(m[1])
    const formatted = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
    const daysAgo = Math.floor((Date.now() - d.getTime()) / 86400000)
    if (daysAgo > 365) {
      const yearsAgo = Math.floor(daysAgo / 365)
      return `This document expired on ${formatted} — ${yearsAgo} year${yearsAgo > 1 ? 's' : ''} ago. It is no longer valid.`
    }
    return `This document expired on ${formatted} — ${daysAgo} day${daysAgo > 1 ? 's' : ''} ago. It is no longer valid.`
  }
  return 'This document has expired and is no longer valid.'
}

function humaniseTamperingReason(reason: string): string {
  if (!reason) return 'Document appearance requires review.'
  const lower = reason.toLowerCase()
  if (lower.includes('hologram') || lower.includes('security feature'))
    return 'A security feature on the document appears to be missing or altered.'
  if (lower.includes('opacity') || lower.includes('ink') || lower.includes('stamp'))
    return 'Ink or stamp patterns on the document appear inconsistent with a genuine document.'
  if (lower.includes('character') || lower.includes('alignment') || lower.includes('text edit'))
    return 'Text on the document appears to have been altered — characters are misaligned.'
  if (lower.includes('ela') || lower.includes('anomalous block'))
    return 'Image analysis detected possible editing or alteration in the document.'
  if (lower.includes('font'))
    return 'Font inconsistencies detected — the document may not be genuine.'
  return 'The document appearance has characteristics that require physical examination.'
}

function humaniseCitizenRegistryReason(reason: string): string {
  if (!reason) return 'Record status requires review.'
  const lower = reason.toLowerCase()
  if (lower.includes('revoked') || lower.includes('cancelled'))
    return 'This document has been cancelled or revoked. It should not be accepted.'
  if (lower.includes('expired'))
    return 'This document is recorded as expired in our database.'
  if (lower.includes('mismatch') || lower.includes('differ'))
    return 'The details on this document do not match the information in our records.'
  if (lower.includes('no record') || lower.includes('not found'))
    return 'No matching record was found in our identity database.'
  return reason
}

// ── Overall verification status ──────────────────────────────────────────────

export function determineVerificationStatus(
  checks: CheckResult[],
  _riskLevel: string,
  _riskScore: number
): VerificationStatus {
  const failedChecks = checks.filter((c) => c.status === 'FAIL')
  const reviewChecks = checks.filter((c) => c.status === 'REVIEW')

  if (failedChecks.some((c) => c.label === 'Security records check')) {
    return {
      status: 'VERIFICATION_FAILED',
      label: 'Security Alert',
      explanation: 'This document or person is flagged in security records. Entry cannot be approved at this checkpoint.',
      recommendation: [
        'Do not allow entry.',
        'Detain the traveler and notify your supervisor immediately.',
        "Record all details and the traveler's response.",
      ],
    }
  }

  if (failedChecks.some((c) => c.label === 'Photo comparison' || c.label === 'Identity records match')) {
    return {
      status: 'VERIFICATION_FAILED',
      label: 'Identity Check Failed',
      explanation: 'The person in front of you does not appear to match the document presented.',
      recommendation: [
        'Compare the person physically with the document photo.',
        'Ask the traveler to explain any discrepancy.',
        'Do not approve entry until identity is confirmed. Refer to supervisor.',
      ],
    }
  }

  if (failedChecks.some((c) => c.label === 'Document validity')) {
    return {
      status: 'VERIFICATION_FAILED',
      label: 'Expired Document',
      explanation: 'The document presented has expired and cannot be accepted.',
      recommendation: [
        'Inform the traveler that the document is expired.',
        'Ask if they have a valid alternative document.',
        'Do not approve entry on an expired document.',
      ],
    }
  }

  if (failedChecks.some((c) => c.label === 'Live person check' || c.label === 'Photo authenticity')) {
    return {
      status: 'RETAKE_REQUIRED',
      label: 'Photo Retake Required',
      explanation: 'The live photo could not be verified reliably. A new photo is needed.',
      recommendation: [
        'Ask the traveler to look directly at the camera.',
        'Retake the live photo in good lighting.',
        'Ensure no screens or printed images are used.',
      ],
    }
  }

  if (failedChecks.length > 0 || reviewChecks.length >= 2) {
    return {
      status: 'MANUAL_CHECK_REQUIRED',
      label: 'Manual Review Required',
      explanation: 'One or more checks require officer review before verification can be completed.',
      recommendation: [
        'Review each flagged item carefully.',
        'Compare the document physically with the person.',
        'Refer to your supervisor if any concern remains unresolved.',
      ],
    }
  }

  if (reviewChecks.length === 1) {
    return {
      status: 'MANUAL_CHECK_REQUIRED',
      label: 'Review Recommended',
      explanation: 'Most checks passed. One item requires your attention before completing verification.',
      recommendation: [
        'Review the flagged item below.',
        'Complete verification once satisfied.',
      ],
    }
  }

  return {
    status: 'VERIFIED',
    label: 'All Checks Passed',
    explanation: 'All verification checks completed successfully. No issues detected.',
    recommendation: ['Verification can be completed.'],
  }
}

export function translateRiskLevel(level: string, _score: number): string {
  // Handle both "LOW_RISK" (backend) and "LOW" (older format)
  const normalised = level.replace('_RISK', '')
  switch (normalised) {
    case 'LOW': return 'Low — no significant concerns'
    case 'MEDIUM': return 'Medium — some items require attention'
    case 'HIGH': return 'High — immediate review required'
    default: return `Risk level: ${level}`
  }
}
