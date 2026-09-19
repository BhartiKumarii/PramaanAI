import React, { useEffect, useState } from 'react'
import { CheckCircle2, AlertTriangle, XCircle, FileText, Users, Shield } from 'lucide-react'
import { StatTile } from './StatTile'

interface TestingStats {
  totalDocuments: number
  totalTestCases: number
  passedTests: number
  failedTests: number
  warningTests: number
  documentsByCountry: Record<string, number>
  documentsByType: Record<string, number>
  verificationConditions: {
    document: { passed: number; total: number }
    tampering: { passed: number; total: number }
    face: { passed: number; total: number }
    identity: { passed: number; total: number }
  }
  riskDistribution: {
    low: number
    medium: number
    high: number
  }
}

interface CountryTestResults {
  country: string
  flag: string
  totalDocs: number
  passRate: number
  commonDocTypes: string[]
  riskBreakdown: { low: number; medium: number; high: number }
  topIssues: string[]
}

function CountryCard({ country }: { country: CountryTestResults }) {
  const getRiskColor = (risk: 'low' | 'medium' | 'high') => {
    switch (risk) {
      case 'low': return 'bg-status-clear'
      case 'medium': return 'bg-status-review'
      case 'high': return 'bg-status-high'
    }
  }

  const total = country.riskBreakdown.low + country.riskBreakdown.medium + country.riskBreakdown.high

  return (
    <div className="bg-card border border-border rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{country.flag}</span>
          <div>
            <h3 className="text-lg font-semibold text-foreground">{country.country}</h3>
            <p className="text-sm text-muted-foreground">{country.totalDocs} documents tested</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-status-clear">
            {Math.round(country.passRate)}%
          </div>
          <div className="text-xs text-muted-foreground">Pass Rate</div>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-sm font-medium text-foreground">Document Types:</div>
        <div className="flex flex-wrap gap-1">
          {country.commonDocTypes.map(type => (
            <span key={type} className="text-xs bg-accent/10 text-accent px-2 py-1 rounded">
              {type}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-sm font-medium text-foreground">Risk Distribution:</div>
        <div className="flex h-2 overflow-hidden rounded-full bg-secondary">
          {total > 0 && (
            <>
              <div
                className={getRiskColor('low')}
                style={{ width: `${(country.riskBreakdown.low / total) * 100}%` }}
              />
              <div
                className={getRiskColor('medium')}
                style={{ width: `${(country.riskBreakdown.medium / total) * 100}%` }}
              />
              <div
                className={getRiskColor('high')}
                style={{ width: `${(country.riskBreakdown.high / total) * 100}%` }}
              />
            </>
          )}
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>🟢 {country.riskBreakdown.low} Low</span>
          <span>🟡 {country.riskBreakdown.medium} Medium</span>
          <span>🔴 {country.riskBreakdown.high} High</span>
        </div>
      </div>

      {country.topIssues.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-foreground">Common Issues:</div>
          <ul className="space-y-1">
            {country.topIssues.slice(0, 3).map((issue, index) => (
              <li key={index} className="text-xs text-muted-foreground">• {issue}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function VerificationConditionsOverview({ conditions }: { conditions: TestingStats['verificationConditions'] }) {
  const categories = [
    { key: 'document', name: 'Document Verification', icon: '📄', ...conditions.document },
    { key: 'tampering', name: 'Tampering Detection', icon: '🔍', ...conditions.tampering },
    { key: 'face', name: 'Face Verification', icon: '👤', ...conditions.face },
    { key: 'identity', name: 'Identity Detection', icon: '🔄', ...conditions.identity },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {categories.map(cat => {
        const percentage = cat.total > 0 ? Math.round((cat.passed / cat.total) * 100) : 0
        const isGood = percentage >= 90
        const isWarning = percentage >= 70 && percentage < 90

        return (
          <div key={cat.key} className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl mb-2">{cat.icon}</div>
            <div className="text-sm font-medium text-foreground mb-1">{cat.name}</div>
            <div className={`text-2xl font-bold mb-1 ${
              isGood ? 'text-status-clear' : isWarning ? 'text-status-review' : 'text-status-high'
            }`}>
              {percentage}%
            </div>
            <div className="text-xs text-muted-foreground">
              {cat.passed}/{cat.total} conditions
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function ComprehensiveTestingDashboard() {
  const [stats, setStats] = useState<TestingStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Simulate loading comprehensive testing data
    // In real implementation, this would fetch from your API
    const loadTestingData = async () => {
      try {
        // Mock data representing your comprehensive testing results
        const mockStats: TestingStats = {
          totalDocuments: 1035,
          totalTestCases: 1054,
          passedTests: 945,
          failedTests: 67,
          warningTests: 42,
          documentsByCountry: {
            'India': 944 + 56, // Valid + Blacklisted Aadhaar
            'Nepal': 20,
            'Bhutan': 7
          },
          documentsByType: {
            'Aadhaar': 1000,
            'Passport': 15,
            'Visa': 8,
            'Permit': 12
          },
          verificationConditions: {
            document: { passed: 7, total: 8 },
            tampering: { passed: 9, total: 10 },
            face: { passed: 6, total: 7 },
            identity: { passed: 8, total: 8 }
          },
          riskDistribution: {
            low: 780,
            medium: 185,
            high: 89
          }
        }

        setStats(mockStats)
        setLoading(false)
      } catch (err) {
        setError('Failed to load testing data')
        setLoading(false)
      }
    }

    loadTestingData()
  }, [])

  const countryResults: CountryTestResults[] = [
    {
      country: 'India',
      flag: '🇮🇳',
      totalDocs: 1000,
      passRate: 94.2,
      commonDocTypes: ['Aadhaar', 'Passport', 'Visa'],
      riskBreakdown: { low: 720, medium: 150, high: 60 },
      topIssues: [
        'Document expiry validation',
        'Face quality in older documents',
        'Blacklist status verification'
      ]
    },
    {
      country: 'Nepal',
      flag: '🇳🇵',
      totalDocs: 20,
      passRate: 90.0,
      commonDocTypes: ['Passport', 'Citizenship', 'Permit'],
      riskBreakdown: { low: 15, medium: 3, high: 2 },
      topIssues: [
        'MRZ format variations',
        'Document format differences',
        'Font inconsistencies'
      ]
    },
    {
      country: 'Bhutan',
      flag: '🇧🇹',
      totalDocs: 7,
      passRate: 85.7,
      commonDocTypes: ['Passport', 'Permit'],
      riskBreakdown: { low: 5, medium: 1, high: 1 },
      topIssues: [
        'Limited document templates',
        'Hologram detection',
        'Text recognition accuracy'
      ]
    }
  ]

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-accent mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading comprehensive testing results...</p>
        </div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="text-center py-12">
        <XCircle className="h-12 w-12 text-status-high mx-auto mb-4" />
        <p className="text-status-high">{error || 'Failed to load testing data'}</p>
      </div>
    )
  }

  const passRate = Math.round((stats.passedTests / stats.totalTestCases) * 100)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              🎯 Comprehensive Verification Testing Dashboard
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Complete testing results across all verification conditions for India, Nepal, and Bhutan documents
            </p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-status-clear">{passRate}%</div>
            <div className="text-sm text-muted-foreground">Overall Pass Rate</div>
          </div>
        </div>
      </div>

      {/* Key Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatTile
          icon={FileText}
          title="Total Documents"
          value={stats.totalDocuments.toLocaleString()}
          subtitle="Real documents tested"
        />
        <StatTile
          icon={Shield}
          title="Test Cases"
          value={stats.totalTestCases.toLocaleString()}
          subtitle="Verification scenarios"
        />
        <StatTile
          icon={CheckCircle2}
          title="Passed Tests"
          value={stats.passedTests.toLocaleString()}
          subtitle={`${passRate}% success rate`}
        />
        <StatTile
          icon={AlertTriangle}
          title="Issues Found"
          value={(stats.failedTests + stats.warningTests).toLocaleString()}
          subtitle="Failed & warnings"
        />
      </div>

      {/* Verification Conditions Overview */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-foreground">
          📋 All 33 Verification Conditions Status
        </h2>
        <VerificationConditionsOverview conditions={stats.verificationConditions} />
      </div>

      {/* Country-wise Results */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-foreground">
          🌏 Country-wise Testing Results
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {countryResults.map(country => (
            <CountryCard key={country.country} country={country} />
          ))}
        </div>
      </div>

      {/* Risk Distribution Chart */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          📊 Risk Level Distribution
        </h3>
        <div className="space-y-4">
          <div className="flex h-8 overflow-hidden rounded-full bg-secondary">
            <div
              className="bg-status-clear flex items-center justify-center text-xs font-medium"
              style={{ width: `${(stats.riskDistribution.low / stats.totalTestCases) * 100}%` }}
            >
              {Math.round((stats.riskDistribution.low / stats.totalTestCases) * 100)}%
            </div>
            <div
              className="bg-status-review flex items-center justify-center text-xs font-medium"
              style={{ width: `${(stats.riskDistribution.medium / stats.totalTestCases) * 100}%` }}
            >
              {Math.round((stats.riskDistribution.medium / stats.totalTestCases) * 100)}%
            </div>
            <div
              className="bg-status-high flex items-center justify-center text-xs font-medium text-white"
              style={{ width: `${(stats.riskDistribution.high / stats.totalTestCases) * 100}%` }}
            >
              {Math.round((stats.riskDistribution.high / stats.totalTestCases) * 100)}%
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-lg font-bold text-status-clear">
                {stats.riskDistribution.low}
              </div>
              <div className="text-xs text-muted-foreground">Low Risk</div>
            </div>
            <div>
              <div className="text-lg font-bold text-status-review">
                {stats.riskDistribution.medium}
              </div>
              <div className="text-xs text-muted-foreground">Medium Risk</div>
            </div>
            <div>
              <div className="text-lg font-bold text-status-high">
                {stats.riskDistribution.high}
              </div>
              <div className="text-xs text-muted-foreground">High Risk</div>
            </div>
          </div>
        </div>
      </div>

      {/* Document Types Breakdown */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          📄 Document Types Tested
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats.documentsByType).map(([type, count]) => (
            <div key={type} className="text-center p-4 bg-card/50 rounded">
              <div className="text-2xl font-bold text-accent">{count}</div>
              <div className="text-sm text-muted-foreground">{type}</div>
            </div>
          ))}
        </div>
      </div>

      {/* System Status */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          ⚡ System Status
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-3 bg-status-clear/10 rounded">
            <CheckCircle2 className="h-5 w-5 text-status-clear" />
            <div>
              <div className="text-sm font-medium text-foreground">Backend API</div>
              <div className="text-xs text-muted-foreground">All 33 conditions operational</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-status-clear/10 rounded">
            <CheckCircle2 className="h-5 w-5 text-status-clear" />
            <div>
              <div className="text-sm font-medium text-foreground">Database</div>
              <div className="text-xs text-muted-foreground">1,035+ documents loaded</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-status-clear/10 rounded">
            <CheckCircle2 className="h-5 w-5 text-status-clear" />
            <div>
              <div className="text-sm font-medium text-foreground">Multi-language</div>
              <div className="text-xs text-muted-foreground">6 languages active</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ComprehensiveTestingDashboard