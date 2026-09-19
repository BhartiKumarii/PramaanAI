
interface VerificationCondition {
  conditionType: string
  status: 'PASS' | 'FAIL' | 'WARNING'
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  message: string
  details: Record<string, any>
  officerActionRequired: boolean
}

interface ComprehensiveVerificationResult {
  overallStatus: string
  riskLevel: string
  confidenceScore: number
  verificationSummary: string
  documentConditions: VerificationCondition[]
  tamperingConditions: VerificationCondition[]
  faceConditions: VerificationCondition[]
  identityConditions: VerificationCondition[]
  officerRecommendations: string[]
  requiredActions: string[]
  technicalDetails: Record<string, any>
}

interface Props {
  result: ComprehensiveVerificationResult
  documentType: string
  nationality: string
}

function ConditionRow({ condition }: { condition: VerificationCondition }) {
  const statusColor = {
    PASS: 'text-status-clear',
    FAIL: 'text-status-high',
    WARNING: 'text-status-review'
  }[condition.status]

  const severityIcon = {
    LOW: '🟢',
    MEDIUM: '🟡',
    HIGH: '🔴'
  }[condition.severity]

  const conditionName = condition.conditionType
    .replace(/^(DOCUMENT_|TAMPERING_|FACE_|IDENTITY_)/, '')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, l => l.toUpperCase())

  return (
    <div className="border-b border-border py-3 last:border-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm">{severityIcon}</span>
          <span className="text-sm font-medium text-foreground">{conditionName}</span>
          {condition.officerActionRequired && (
            <span className="text-xs bg-status-review/10 text-status-review px-2 py-1 rounded">
              Officer Review Required
            </span>
          )}
        </div>
        <span className={`text-xs font-semibold uppercase tracking-wide ${statusColor}`}>
          {condition.status}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{condition.message}</p>
      {Object.keys(condition.details).length > 0 && (
        <details className="mt-2">
          <summary className="text-xs text-accent cursor-pointer hover:underline">
            Technical Details
          </summary>
          <pre className="text-xs text-muted-foreground mt-1 bg-card/50 p-2 rounded overflow-auto">
            {JSON.stringify(condition.details, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}

function ConditionCategory({
  title,
  conditions,
  icon
}: {
  title: string
  conditions: VerificationCondition[]
  icon: string
}) {
  const passedCount = conditions.filter(c => c.status === 'PASS').length
  const failedCount = conditions.filter(c => c.status === 'FAIL').length
  const warningCount = conditions.filter(c => c.status === 'WARNING').length

  return (
    <div className="bg-card border border-border rounded-lg">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{icon}</span>
            <h3 className="text-lg font-semibold text-foreground">{title}</h3>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-status-clear">✓ {passedCount}</span>
            <span className="text-status-review">⚠ {warningCount}</span>
            <span className="text-status-high">✗ {failedCount}</span>
          </div>
        </div>
      </div>
      <div className="p-4">
        {conditions.map((condition, index) => (
          <ConditionRow key={index} condition={condition} />
        ))}
      </div>
    </div>
  )
}

export function ComprehensiveVerificationPanel({ result, documentType, nationality }: Props) {
  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case 'HIGH': return 'text-status-high'
      case 'MEDIUM': return 'text-status-review'
      case 'LOW': return 'text-status-clear'
      default: return 'text-muted-foreground'
    }
  }

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case 'VERIFIED': return 'text-status-clear'
      case 'REVIEW_REQUIRED': return 'text-status-review'
      case 'REJECTED': return 'text-status-high'
      default: return 'text-muted-foreground'
    }
  }

  const getDocumentTypeFlag = (nationality: string) => {
    const flags: Record<string, string> = {
      'India': '🇮🇳',
      'Nepal': '🇳🇵',
      'Bhutan': '🇧🇹',
      'Indian': '🇮🇳',
      'Nepali': '🇳🇵',
      'Nepalese': '🇳🇵',
      'Bhutanese': '🇧🇹'
    }
    return flags[nationality] || '🌏'
  }

  return (
    <div className="space-y-6">
      {/* Overall Status Header */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{getDocumentTypeFlag(nationality)}</span>
            <div>
              <h2 className="text-xl font-bold text-foreground">
                Comprehensive Verification Results
              </h2>
              <p className="text-sm text-muted-foreground">
                {documentType} • {nationality} • All 33 conditions verified
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-2xl font-bold ${getOverallStatusColor(result.overallStatus)}`}>
              {result.overallStatus.replace('_', ' ')}
            </div>
            <div className={`text-sm font-semibold ${getRiskLevelColor(result.riskLevel)}`}>
              {result.riskLevel} RISK
            </div>
            <div className="text-xs text-muted-foreground">
              Confidence: {Math.round(result.confidenceScore * 100)}%
            </div>
          </div>
        </div>

        <div className="p-4 bg-card/50 rounded border">
          <p className="text-sm text-foreground">{result.verificationSummary}</p>
        </div>
      </div>

      {/* Officer Guidance Section */}
      {(result.officerRecommendations.length > 0 || result.requiredActions.length > 0) && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            👮 Officer Guidance
          </h3>

          {result.requiredActions.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-status-high mb-2">⚠️ Required Actions:</h4>
              <ul className="space-y-1">
                {result.requiredActions.map((action, index) => (
                  <li key={index} className="text-sm text-foreground bg-status-high/10 p-2 rounded">
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.officerRecommendations.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-2">💡 Recommendations:</h4>
              <ul className="space-y-1">
                {result.officerRecommendations.map((rec, index) => (
                  <li key={index} className="text-sm text-muted-foreground">
                    • {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Verification Conditions by Category */}
      <div className="space-y-6">
        <ConditionCategory
          title="Document Verification"
          conditions={result.documentConditions}
          icon="📄"
        />

        <ConditionCategory
          title="Tampering Detection"
          conditions={result.tamperingConditions}
          icon="🔍"
        />

        <ConditionCategory
          title="Face Verification"
          conditions={result.faceConditions}
          icon="👤"
        />

        <ConditionCategory
          title="Multiple Identity Detection"
          conditions={result.identityConditions}
          icon="🔄"
        />
      </div>

      {/* Technical Details */}
      <div className="bg-card border border-border rounded-lg p-6">
        <details>
          <summary className="text-lg font-semibold text-foreground cursor-pointer hover:text-accent flex items-center gap-2">
            🔧 Technical Details & Audit Trail
          </summary>
          <div className="mt-4 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div className="p-3 bg-card/50 rounded">
                <div className="text-lg font-bold text-foreground">
                  {result.technicalDetails.total_conditions_checked || 33}
                </div>
                <div className="text-xs text-muted-foreground">Total Conditions</div>
              </div>
              <div className="p-3 bg-card/50 rounded">
                <div className="text-lg font-bold text-status-clear">
                  {result.technicalDetails.conditions_by_status?.passed || 0}
                </div>
                <div className="text-xs text-muted-foreground">Passed</div>
              </div>
              <div className="p-3 bg-card/50 rounded">
                <div className="text-lg font-bold text-status-review">
                  {result.technicalDetails.conditions_by_status?.warnings || 0}
                </div>
                <div className="text-xs text-muted-foreground">Warnings</div>
              </div>
              <div className="p-3 bg-card/50 rounded">
                <div className="text-lg font-bold text-status-high">
                  {result.technicalDetails.conditions_by_status?.failed || 0}
                </div>
                <div className="text-xs text-muted-foreground">Failed</div>
              </div>
            </div>

            <div className="text-xs text-muted-foreground">
              <strong>Verification Timestamp:</strong> {result.technicalDetails.verification_timestamp}
            </div>

            <pre className="text-xs bg-card/30 p-4 rounded overflow-auto">
              {JSON.stringify(result.technicalDetails, null, 2)}
            </pre>
          </div>
        </details>
      </div>
    </div>
  )
}

export default ComprehensiveVerificationPanel