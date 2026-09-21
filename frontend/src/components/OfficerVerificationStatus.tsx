import { useState } from 'react'
import { translateVerificationSignals, determineVerificationStatus, translateRiskLevel } from '../utils/officerTranslations'

interface OfficerVerificationStatusProps {
  verification: any
  risk: {
    level: string
    score: number
    decision: string
  }
}

function VerificationStatusBadge({ status, label }: { status: string; label: string }) {
  const config: Record<string, { cls: string; icon: string }> = {
    VERIFIED:               { cls: 'bg-status-clear-bg text-status-clear border-status-clear/30',   icon: '✓' },
    MANUAL_CHECK_REQUIRED:  { cls: 'bg-status-review-bg text-status-review border-status-review/30', icon: '⚠' },
    VERIFICATION_FAILED:    { cls: 'bg-status-high-bg text-status-high border-status-high/30',       icon: '✕' },
    RETAKE_REQUIRED:        { cls: 'bg-chart-1/10 text-chart-1 border-chart-1/30',                   icon: '↺' },
  }
  const { cls, icon } = config[status] ?? { cls: 'bg-secondary text-muted-foreground border-border', icon: '?' }
  return (
    <div className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold ${cls}`}>
      <span className="text-base">{icon}</span>
      {label}
    </div>
  )
}

function CheckResultRow({ check }: { check: ReturnType<typeof translateVerificationSignals>[number] }) {
  const [expanded, setExpanded] = useState(false)
  const color =
    check.status === 'PASS' ? 'text-status-clear' : check.status === 'REVIEW' ? 'text-status-review' : 'text-status-high'

  return (
    <div className="border-b border-border last:border-0">
      <button
        className="flex w-full items-start gap-3 py-3 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className={`mt-0.5 shrink-0 text-base font-bold ${color}`}>{check.icon}</span>
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">{check.label}</p>
          <p className="text-xs text-muted-foreground">{check.explanation}</p>
        </div>
        <span className="mt-1 shrink-0 text-xs text-muted-foreground">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="pb-3 pl-7 space-y-1">
          {check.status !== 'PASS' && (
            <p className="text-xs font-medium text-foreground">
              What to do: <span className="font-normal text-muted-foreground">{check.action}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function OfficerVerificationStatus({ verification, risk }: OfficerVerificationStatusProps) {
  const [showDiagnostics, setShowDiagnostics] = useState(false)

  if (!verification) {
    return (
      <div className="rounded-lg border border-border bg-card p-6">
        <p className="text-sm text-muted-foreground">No verification data available for this case.</p>
      </div>
    )
  }

  const checks = translateVerificationSignals(verification)
  const verificationStatus = determineVerificationStatus(checks, risk.level, risk.score)
  const riskDescription = translateRiskLevel(risk.level, risk.score)

  // Extract readable OCR fields
  const ocr = verification.ocr?.fields ?? {}
  const docNumber =
    ocr.passport_number ?? ocr.license_number ?? ocr.document_number ?? ocr.visa_number ?? ocr.permit_number ?? null

  return (
    <div className="space-y-4">
      {/* Overall Status */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <VerificationStatusBadge status={verificationStatus.status} label={verificationStatus.label} />
          <span className={`text-xs font-medium ${
            risk.level.includes('HIGH') ? 'text-status-high' :
            risk.level.includes('MEDIUM') ? 'text-status-review' : 'text-status-clear'
          }`}>
            {riskDescription}
          </span>
        </div>

        <p className="mt-3 text-sm text-foreground">{verificationStatus.explanation}</p>

        {verificationStatus.recommendation.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recommended actions</p>
            <ol className="mt-1.5 space-y-1">
              {verificationStatus.recommendation.map((step, i) => (
                <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                  <span className="shrink-0 font-medium text-foreground">{i + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* Person / document info */}
      {(ocr.name || ocr.nationality || verification.document_type || docNumber) && (
        <div className="rounded-lg border border-border bg-card p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Identity Details</p>
          <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {ocr.name && (
              <div>
                <dt className="text-xs text-muted-foreground">Name</dt>
                <dd className="text-sm font-medium text-foreground">{ocr.name}</dd>
              </div>
            )}
            {ocr.nationality && (
              <div>
                <dt className="text-xs text-muted-foreground">Nationality</dt>
                <dd className="text-sm font-medium text-foreground">{ocr.nationality}</dd>
              </div>
            )}
            {verification.document_type && (
              <div>
                <dt className="text-xs text-muted-foreground">Document type</dt>
                <dd className="text-sm font-medium text-foreground capitalize">{verification.document_type.replace(/_/g, ' ')}</dd>
              </div>
            )}
            {docNumber && (
              <div>
                <dt className="text-xs text-muted-foreground">Document number</dt>
                <dd className="font-mono text-sm font-medium text-foreground">{maskDocNumber(docNumber)}</dd>
              </div>
            )}
            {ocr.date_of_birth && (
              <div>
                <dt className="text-xs text-muted-foreground">Date of birth</dt>
                <dd className="text-sm font-medium text-foreground">{ocr.date_of_birth}</dd>
              </div>
            )}
            {ocr.date_of_expiry && (
              <div>
                <dt className="text-xs text-muted-foreground">Document expiry</dt>
                <dd className="text-sm font-medium text-foreground">{ocr.date_of_expiry}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {/* Check results */}
      <div className="rounded-lg border border-border bg-card p-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Verification Checks</p>
        <div className="divide-y divide-border">
          {checks.map((check, i) => (
            <CheckResultRow key={i} check={check} />
          ))}
        </div>
      </div>

      {/* System diagnostics — collapsed, clearly labelled internal */}
      <div className="rounded-lg border border-border bg-secondary/40 p-4">
        <button
          onClick={() => setShowDiagnostics((v) => !v)}
          className="flex w-full items-center gap-2 text-left"
        >
          <span className="text-xs text-muted-foreground">{showDiagnostics ? '▲' : '▶'}</span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            System Diagnostics — Internal Use Only
          </span>
        </button>

        {showDiagnostics && (
          <div className="mt-4 space-y-4 text-xs text-muted-foreground">
            <p className="italic">Raw AI/ML output. Not for use in officer decisions.</p>

            {verification.ocr && (
              <div>
                <p className="font-semibold text-foreground">OCR Analysis</p>
                <p>Confidence: {Math.round(verification.ocr.ocr_confidence * 100)}%</p>
                <p>Fields extracted: {Object.keys(verification.ocr.fields).join(', ')}</p>
              </div>
            )}
            {verification.tampering && (
              <div>
                <p className="font-semibold text-foreground">Forensic Analysis (ELA)</p>
                <p>Risk: {Math.round(verification.tampering.tampering_risk * 100)}%</p>
                {verification.tampering.findings?.[0] && <p>Finding: {verification.tampering.findings[0].reason}</p>}
              </div>
            )}
            {verification.face && (
              <div>
                <p className="font-semibold text-foreground">Face Recognition</p>
                <p>Cosine similarity: {verification.face.similarity}</p>
                <p>Match threshold: 0.75 | Confidence: {verification.face.confidence}</p>
              </div>
            )}
            {verification.liveness && (
              <div>
                <p className="font-semibold text-foreground">Liveness Detection</p>
                <p>Status: {verification.liveness.status} | Score: {verification.liveness.score ?? 'N/A'}</p>
              </div>
            )}
            {verification.deepfake && (
              <div>
                <p className="font-semibold text-foreground">Deepfake Analysis</p>
                <p>Status: {verification.deepfake.status} | Score: {verification.deepfake.score ?? 'N/A'}</p>
              </div>
            )}
            {verification.identity_graph && (
              <div>
                <p className="font-semibold text-foreground">Identity Graph</p>
                <p>Status: {verification.identity_graph.status} | Cluster size: {verification.identity_graph.cluster_size ?? 1}</p>
              </div>
            )}
            <div>
              <p className="font-semibold text-foreground">Risk Engine</p>
              <p>Score: {risk.score}/100 | Level: {risk.level} | Decision: {risk.decision}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function maskDocNumber(doc: string): string {
  if (doc.length <= 6) return doc
  return doc.slice(0, 3) + '****' + doc.slice(-3)
}
