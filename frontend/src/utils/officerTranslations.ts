/**
 * Translation layer from technical AI/ML terminology to officer-friendly language
 */

export interface VerificationStatus {
  status: 'VERIFIED' | 'MANUAL_CHECK_REQUIRED' | 'VERIFICATION_FAILED' | 'RETAKE_REQUIRED'
  explanation: string
  recommendation: string[]
}

export interface CheckResult {
  label: string
  status: 'PASS' | 'REVIEW' | 'FAIL'
  explanation: string
  icon: '✓' | '⚠' | '✗'
  technical?: string // Original technical message for Technical Evidence section
}

/**
 * Translate technical verification signals to human-readable check results
 */
export function translateVerificationSignals(verification: any): CheckResult[] {
  const checks: CheckResult[] = []

  // OCR Extraction → Document Information
  if (verification.ocr) {
    const confidence = Math.round(verification.ocr.ocr_confidence * 100)
    checks.push({
      label: "Document information",
      status: confidence >= 70 ? 'PASS' : confidence >= 40 ? 'REVIEW' : 'FAIL',
      explanation: confidence >= 70
        ? "Document details are clearly readable"
        : confidence >= 40
        ? "Some document details are unclear"
        : "Document details could not be read reliably",
      icon: confidence >= 70 ? '✓' : confidence >= 40 ? '⚠' : '✗',
      technical: `OCR confidence: ${confidence}%`
    })
  }

  // Document Validation (MRZ/Verhoeff) → Document Format Check
  if (verification.validation) {
    checks.push({
      label: "Document format",
      status: verification.validation.status === 'PASS' ? 'PASS' : 'FAIL',
      explanation: verification.validation.status === 'PASS'
        ? "Document format appears correct"
        : "Document format has issues requiring review",
      icon: verification.validation.status === 'PASS' ? '✓' : '✗',
      technical: `MRZ/Verhoeff validation: ${verification.validation.status}`
    })
  }

  // Document Forensics (ELA) → Document Appearance Check
  if (verification.tampering) {
    const riskPercent = Math.round(verification.tampering.tampering_risk * 100)
    checks.push({
      label: "Document appearance",
      status: riskPercent <= 25 ? 'PASS' : riskPercent <= 50 ? 'REVIEW' : 'FAIL',
      explanation: riskPercent <= 25
        ? "No obvious alteration detected"
        : riskPercent <= 50
        ? "Document appearance needs review"
        : "Possible alteration detected",
      icon: riskPercent <= 25 ? '✓' : riskPercent <= 50 ? '⚠' : '✗',
      technical: `ELA anomaly risk: ${riskPercent}%`
    })
  }

  // Face Match → Photo Comparison
  if (verification.face) {
    checks.push({
      label: "Photo comparison",
      status: verification.face.match ? 'PASS' : 'FAIL',
      explanation: verification.face.match
        ? "Live photo matches document photo"
        : "Live photo does not match document photo",
      icon: verification.face.match ? '✓' : '✗',
      technical: `Face similarity: ${verification.face.similarity}, threshold: 0.75`
    })
  }

  // Liveness Check → Live Person Check
  if (verification.liveness) {
    const status = verification.liveness.status
    checks.push({
      label: "Live person check",
      status: status === 'LIVE' ? 'PASS' : status === 'SUSPECTED_SPOOF' ? 'FAIL' : 'REVIEW',
      explanation: status === 'LIVE'
        ? "Live person confirmed"
        : status === 'SUSPECTED_SPOOF'
        ? "Photo appears to be from screen or printed image"
        : "Live person check uncertain",
      icon: status === 'LIVE' ? '✓' : status === 'SUSPECTED_SPOOF' ? '✗' : '⚠',
      technical: `Liveness: ${status}`
    })
  }

  // Deepfake Heuristic → Photo Authenticity Check
  if (verification.deepfake && verification.deepfake.status === 'ANALYZED') {
    const score = verification.deepfake.score || 0
    checks.push({
      label: "Photo authenticity",
      status: score <= 0.3 ? 'PASS' : score <= 0.7 ? 'REVIEW' : 'FAIL',
      explanation: score <= 0.3
        ? "Photo appears authentic"
        : score <= 0.7
        ? "Photo authenticity uncertain"
        : "Photo may be artificially generated",
      icon: score <= 0.3 ? '✓' : score <= 0.7 ? '⚠' : '✗',
      technical: `Deepfake score: ${score.toFixed(2)}`
    })
  }

  // Registry/Blacklist → Security Record Check
  if (verification.registry) {
    checks.push({
      label: "Security records",
      status: verification.registry.status === 'HIT' ? 'FAIL' : 'PASS',
      explanation: verification.registry.status === 'HIT'
        ? "Security alert found - requires manual review"
        : "No security alerts found",
      icon: verification.registry.status === 'HIT' ? '✗' : '✓',
      technical: `Registry lookup: ${verification.registry.status}`
    })
  }

  // Identity Graph → Previous Identity Records
  if (verification.identity_graph) {
    checks.push({
      label: "Previous identity records",
      status: verification.identity_graph.status === 'CLUSTER_FOUND' ? 'REVIEW' : 'PASS',
      explanation: verification.identity_graph.status === 'CLUSTER_FOUND'
        ? "This person appears in multiple identity records"
        : "No conflicting identity records found",
      icon: verification.identity_graph.status === 'CLUSTER_FOUND' ? '⚠' : '✓',
      technical: `Identity graph: ${verification.identity_graph.status}`
    })
  }

  // Nepal Visa Specific Checks
  if (verification.nepal_visa_conditions) {
    for (const condition of verification.nepal_visa_conditions) {
      if (condition.condition_type === 'NEPAL_VISA_FORMAT_DETECTED') {
        checks.push({
          label: "Visa format",
          status: 'PASS',
          explanation: "Nepal visa format identified successfully",
          icon: '✓',
          technical: `Format: ${condition.details.format_type}, confidence: ${condition.details.confidence}`
        })
      } else if (condition.condition_type === 'NEPAL_VISA_DATES_VALID') {
        checks.push({
          label: "Visa validity",
          status: 'PASS',
          explanation: "Visa is currently valid",
          icon: '✓',
          technical: `Valid until: ${condition.details.validity_end}`
        })
      } else if (condition.condition_type === 'NEPAL_VISA_EXPIRED') {
        checks.push({
          label: "Visa validity",
          status: 'FAIL',
          explanation: "Visa has expired",
          icon: '✗',
          technical: `Expired on: ${condition.details.validity_end}`
        })
      } else if (condition.condition_type === 'NEPAL_VISA_PASSPORT_MATCH') {
        checks.push({
          label: "Passport number match",
          status: 'PASS',
          explanation: "Visa passport number matches provided passport",
          icon: '✓',
          technical: `Visa passport: ${condition.details.visa_passport}`
        })
      } else if (condition.condition_type === 'NEPAL_VISA_PASSPORT_MISMATCH') {
        checks.push({
          label: "Passport number match",
          status: 'FAIL',
          explanation: "Visa passport number does not match provided passport",
          icon: '✗',
          technical: `Visa: ${condition.details.visa_passport}, Passport: ${condition.details.document_passport}`
        })
      } else if (condition.condition_type === 'NEPAL_VISA_QR_VALID') {
        checks.push({
          label: "QR code verification",
          status: 'PASS',
          explanation: "QR code information matches visa details",
          icon: '✓',
          technical: `QR validation: ${condition.details.validation}`
        })
      } else if (condition.condition_type === 'NEPAL_VISA_QR_MISMATCH') {
        checks.push({
          label: "QR code verification",
          status: 'REVIEW',
          explanation: "QR code information differs from visible details",
          icon: '⚠',
          technical: `QR validation: ${condition.details.validation}`
        })
      }
    }
  }

  // Multilingual Document Processing
  if (verification.multilingual_conditions) {
    for (const condition of verification.multilingual_conditions) {
      if (condition.condition_type === 'DOCUMENT_SCRIPT_DETECTED') {
        checks.push({
          label: "Document script",
          status: 'PASS',
          explanation: condition.message,
          icon: '✓',
          technical: `Script: ${condition.details.primary_script}, confidence: ${condition.details.confidence}`
        })
      } else if (condition.condition_type === 'DOCUMENT_LANGUAGE_DETECTED') {
        checks.push({
          label: "Document language",
          status: 'PASS',
          explanation: condition.message,
          icon: '✓',
          technical: `Language: ${condition.details.primary_language}, method: ${condition.details.detection_method}`
        })
      } else if (condition.condition_type === 'MULTILINGUAL_OCR_SUCCESSFUL') {
        checks.push({
          label: "Text extraction",
          status: 'PASS',
          explanation: "Document text extracted with language-aware processing",
          icon: '✓',
          technical: `OCR confidence: ${condition.details.ocr_confidence}, languages: ${condition.details.languages_processed?.join(', ')}`
        })
      } else if (condition.condition_type === 'DOCUMENT_SCRIPT_UNCERTAIN') {
        checks.push({
          label: "Document script",
          status: 'REVIEW',
          explanation: "Document script detection uncertain",
          icon: '⚠',
          technical: `Script: ${condition.details.primary_script}, confidence: ${condition.details.confidence}`
        })
      } else if (condition.condition_type === 'MULTILINGUAL_OCR_PARTIAL') {
        checks.push({
          label: "Text extraction",
          status: 'REVIEW',
          explanation: "Some document text extracted, quality could be improved",
          icon: '⚠',
          technical: `OCR confidence: ${condition.details.ocr_confidence}`
        })
      }
    }
  }

  return checks
}

/**
 * Determine overall verification status based on check results and risk level
 */
export function determineVerificationStatus(
  checks: CheckResult[],
  riskLevel: string,
  _riskScore: number
): VerificationStatus {
  const failedChecks = checks.filter(c => c.status === 'FAIL')
  const reviewChecks = checks.filter(c => c.status === 'REVIEW')

  // Critical failures
  if (failedChecks.some(c =>
    c.label === 'Photo comparison' ||
    c.label === 'Security records' ||
    c.label === 'Document format'
  )) {
    return {
      status: 'VERIFICATION_FAILED',
      explanation: 'Critical verification checks have failed.',
      recommendation: [
        'Check the original document against the person',
        'Verify identity through alternative means',
        'Forward for manual review if discrepancies remain'
      ]
    }
  }

  // Photo/image quality issues
  if (failedChecks.some(c =>
    c.label === 'Live person check' ||
    c.label === 'Photo authenticity'
  )) {
    return {
      status: 'RETAKE_REQUIRED',
      explanation: 'Photo quality issues prevent reliable verification.',
      recommendation: [
        'Retake the live photo in better lighting',
        'Ensure only the person is visible in the photo',
        'Check that photo is not from screen or printed image'
      ]
    }
  }

  // Any failed or multiple review items
  if (failedChecks.length > 0 || reviewChecks.length >= 2) {
    return {
      status: 'MANUAL_CHECK_REQUIRED',
      explanation: 'Some checks require officer review before verification can be completed.',
      recommendation: [
        'Compare the person with the document photo',
        'Check the original document for any alterations',
        'Forward for supervisor review if concerns remain'
      ]
    }
  }

  // Single review item or uncertain liveness with low risk
  if (reviewChecks.length === 1 || (riskLevel === 'LOW' && reviewChecks.length === 0)) {
    // Special case: liveness uncertain but everything else OK
    if (reviewChecks.some(c => c.label === 'Live person check')) {
      return {
        status: 'MANUAL_CHECK_REQUIRED',
        explanation: 'Document details appear valid, but live photo verification is uncertain.',
        recommendation: [
          'Retake the live photo',
          'Compare the person with the document photo',
          'Complete verification if identity is confirmed'
        ]
      }
    }

    return {
      status: 'MANUAL_CHECK_REQUIRED',
      explanation: 'Most checks passed, but manual review is recommended.',
      recommendation: [
        'Review flagged items',
        'Complete verification if satisfied with identity confirmation'
      ]
    }
  }

  // All checks passed
  return {
    status: 'VERIFIED',
    explanation: 'All verification checks have passed successfully.',
    recommendation: [
      'Complete verification and allow entry'
    ]
  }
}

/**
 * Get human-readable risk level description
 */
export function translateRiskLevel(level: string, _score: number): string {
  switch (level) {
    case 'LOW':
      return 'Low observed risk'
    case 'MEDIUM':
      return 'Medium observed risk'
    case 'HIGH':
      return 'High observed risk'
    default:
      return `Risk level: ${level}`
  }
}