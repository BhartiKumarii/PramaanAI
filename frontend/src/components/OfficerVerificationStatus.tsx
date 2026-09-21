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

function VerificationStatusBadge({ status }: { status: string }) {
  const config = {
    'VERIFIED': {
      class: 'bg-green-100 text-green-800 border-green-200',
      icon: '✓'
    },
    'MANUAL_CHECK_REQUIRED': {
      class: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      icon: '⚠'
    },
    'VERIFICATION_FAILED': {
      class: 'bg-red-100 text-red-800 border-red-200',
      icon: '✗'
    },
    'RETAKE_REQUIRED': {
      class: 'bg-blue-100 text-blue-800 border-blue-200',
      icon: '📷'
    }
  }[status] || {
    class: 'bg-gray-100 text-gray-800 border-gray-200',
    icon: '?'
  }

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-lg font-semibold ${config.class}`}>
      <span className="text-xl">{config.icon}</span>
      {status.replace(/_/g, ' ')}
    </div>
  )
}

function CheckResultRow({ check }: { check: any }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-3">
        <span className={`text-lg ${
          check.status === 'PASS' ? 'text-green-600' :
          check.status === 'REVIEW' ? 'text-yellow-600' :
          'text-red-600'
        }`}>
          {check.icon}
        </span>
        <span className="font-medium text-gray-900">{check.label}</span>
      </div>
      <span className="text-sm text-gray-600">{check.explanation}</span>
    </div>
  )
}

export function OfficerVerificationStatus({ verification, risk }: OfficerVerificationStatusProps) {
  const [showTechnical, setShowTechnical] = useState(false)

  if (!verification) {
    return (
      <div className="bg-gray-50 rounded-lg p-6">
        <p className="text-gray-600">No verification data available for this case.</p>
      </div>
    )
  }

  const checks = translateVerificationSignals(verification)
  const status = determineVerificationStatus(checks, risk.level, risk.score)
  const riskDescription = translateRiskLevel(risk.level, risk.score)

  return (
    <div className="space-y-6">
      {/* Main Status */}
      <div className="bg-white rounded-lg border p-6">
        <div className="text-center space-y-4">
          <VerificationStatusBadge status={status.status} />

          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Why?</h3>
            <p className="text-gray-700">{status.explanation}</p>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">What should I do?</h3>
            <ol className="text-left text-gray-700 space-y-1">
              {status.recommendation.map((step, index) => (
                <li key={index} className="flex gap-2">
                  <span className="font-medium text-gray-500">{index + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      {/* Person Information */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Person</h3>
        <div className="space-y-2">
          {verification.ocr?.fields?.name && (
            <div className="flex justify-between">
              <span className="font-medium text-gray-600">Name:</span>
              <span className="text-gray-900">{verification.ocr.fields.name}</span>
            </div>
          )}
          {verification.ocr?.fields?.nationality && (
            <div className="flex justify-between">
              <span className="font-medium text-gray-600">Nationality:</span>
              <span className="text-gray-900">{verification.ocr.fields.nationality}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Document type:</span>
            <span className="text-gray-900">{verification.document_type || 'Not specified'}</span>
          </div>
          {(verification.ocr?.fields?.passport_number || verification.ocr?.fields?.document_number) && (
            <div className="flex justify-between">
              <span className="font-medium text-gray-600">Document number:</span>
              <span className="text-gray-900 font-mono">
                {verification.ocr.fields.passport_number || verification.ocr.fields.document_number}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Check Results */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Check Results</h3>
        <div className="space-y-1">
          {checks.map((check, index) => (
            <CheckResultRow key={index} check={check} />
          ))}
        </div>
      </div>

      {/* Risk Level (separate from verification status) */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex justify-between items-center">
          <span className="font-medium text-gray-700">Observed risk level:</span>
          <span className={`font-semibold ${
            risk.level === 'LOW' ? 'text-green-700' :
            risk.level === 'MEDIUM' ? 'text-yellow-700' :
            'text-red-700'
          }`}>
            {riskDescription}
          </span>
        </div>
      </div>

      {/* Technical Evidence (Collapsible) */}
      <div className="bg-white rounded-lg border p-6">
        <button
          onClick={() => setShowTechnical(!showTechnical)}
          className="flex items-center gap-2 w-full text-left"
        >
          <span className="text-gray-500">
            {showTechnical ? '▼' : '▶'}
          </span>
          <h3 className="text-lg font-semibold text-gray-900">Technical Evidence</h3>
        </button>

        {showTechnical && (
          <div className="mt-4 space-y-4 text-sm">
            <p className="text-gray-600 italic">
              Technical diagnostic information for administrators and technical review.
            </p>

            {verification.ocr && (
              <div>
                <h4 className="font-semibold text-gray-800">OCR Analysis</h4>
                <p className="text-gray-700">Confidence: {Math.round(verification.ocr.ocr_confidence * 100)}%</p>
                <p className="text-gray-700">Fields extracted: {Object.keys(verification.ocr.fields).length}</p>
              </div>
            )}

            {verification.tampering && (
              <div>
                <h4 className="font-semibold text-gray-800">Forensic Analysis (ELA)</h4>
                <p className="text-gray-700">Tampering risk: {Math.round(verification.tampering.tampering_risk * 100)}%</p>
                <p className="text-gray-700">Analysis: {verification.tampering.findings[0]?.reason || 'No significant anomalies detected'}</p>
              </div>
            )}

            {verification.face && (
              <div>
                <h4 className="font-semibold text-gray-800">Face Recognition</h4>
                <p className="text-gray-700">Cosine similarity: {verification.face.similarity}</p>
                <p className="text-gray-700">Match threshold: 0.75</p>
                <p className="text-gray-700">Confidence: {verification.face.confidence}</p>
              </div>
            )}

            {verification.liveness && (
              <div>
                <h4 className="font-semibold text-gray-800">Liveness Detection</h4>
                <p className="text-gray-700">Status: {verification.liveness.status}</p>
                <p className="text-gray-700">Score: {verification.liveness.score || 'N/A'}</p>
              </div>
            )}

            {verification.deepfake && (
              <div>
                <h4 className="font-semibold text-gray-800">Deepfake Analysis</h4>
                <p className="text-gray-700">Status: {verification.deepfake.status}</p>
                <p className="text-gray-700">Score: {verification.deepfake.score || 'N/A'}</p>
              </div>
            )}

            {verification.identity_graph && (
              <div>
                <h4 className="font-semibold text-gray-800">Identity Graph</h4>
                <p className="text-gray-700">Status: {verification.identity_graph.status}</p>
                <p className="text-gray-700">Cluster threshold: 0.75</p>
              </div>
            )}

            <div>
              <h4 className="font-semibold text-gray-800">Risk Engine</h4>
              <p className="text-gray-700">Score: {risk.score}/100</p>
              <p className="text-gray-700">Decision: {risk.decision}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}