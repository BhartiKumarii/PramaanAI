import { useNavigate } from 'react-router-dom'
import type { CaseListItem } from '../api/types'
import { StatusBadge, PriorityBadge } from './StatusBadge'

function timeAgo(iso: string | null): string {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.floor(ms / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return d === 1 ? 'yesterday' : `${d}d ago`
}

function isStale(iso: string | null): boolean {
  if (!iso) return false
  return Date.now() - new Date(iso).getTime() > 24 * 60 * 60 * 1000
}

const DOC_LABELS: Record<string, string> = {
  passport: 'Passport',
  national_id: 'National ID',
  visa: 'Visa',
  driving_licence: 'Driving Licence',
  driving_license: 'Driving Licence',
  aadhaar: 'Aadhaar',
  pan_card: 'PAN Card',
  voter_id: 'Voter ID',
  citizenship_certificate: 'Citizenship',
  permit: 'Permit / ILP',
}

const CHECKPOINT_NAMES: Record<string, string> = {
  ATW: 'Attari-Wagah',
  PET: 'Petrapole',
  RAX: 'Raxaul',
  JAI: 'Jaigaon / Phuentsholing',
  GEL: 'Gelephu',
  SMD: 'Samdrup Jongkhar',
}

function riskLabel(level: string | undefined): string {
  if (!level) return '—'
  if (level === 'HIGH_RISK') return 'High Risk'
  if (level === 'MEDIUM_RISK') return 'Medium Risk'
  return 'Low Risk'
}

export function CaseTable({ cases, showSentAt = false }: { cases: CaseListItem[]; showSentAt?: boolean }) {
  const navigate = useNavigate()

  if (cases.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No cases match the current filters.</p>
  }

  return (
    <div className="divide-y divide-border">
      {cases.map((c) => {
        const stale = showSentAt ? isStale(c.sent_at) : false
        const docLabel = DOC_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type ?? '—'
        const checkpointName = CHECKPOINT_NAMES[c.checkpoint_code] ?? c.checkpoint_code

        return (
          <div
            key={c.id}
            onClick={() => navigate(`/console/cases/${c.id}`)}
            className={`group cursor-pointer px-4 py-4 hover:bg-secondary transition-colors ${stale ? 'border-l-2 border-l-status-high' : ''}`}
          >
            {/* Row 1: Case number + badges + time */}
            <div className="flex items-center justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs font-semibold text-foreground bg-secondary border border-border px-2 py-0.5 rounded">
                  {c.case_number}
                </span>
                <StatusBadge status={c.status} />
                <PriorityBadge priority={c.priority} />
                {stale && (
                  <span className="text-xs font-medium text-status-high bg-status-high/10 border border-status-high/30 px-2 py-0.5 rounded">
                    ⚠ Waiting &gt;24h
                  </span>
                )}
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
                {showSentAt ? timeAgo(c.sent_at) : timeAgo(c.created_at)}
              </span>
            </div>

            {/* Row 2: Traveler + doc type + nationality + risk */}
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <span className="text-sm font-semibold text-foreground">
                {c.traveler_name ?? 'Unknown traveller'}
              </span>
              {c.nationality && (
                <span className="text-xs font-medium text-muted-foreground bg-secondary border border-border px-2 py-0.5 rounded-full">
                  {c.nationality.toUpperCase()}
                </span>
              )}
              <span className="text-xs font-medium text-accent bg-accent/10 border border-accent/20 px-2 py-0.5 rounded-full">
                {docLabel}
              </span>
              {c.risk_level && (
                <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${
                  c.risk_level === 'HIGH_RISK'
                    ? 'bg-status-high/10 border-status-high/30 text-status-high'
                    : c.risk_level === 'MEDIUM_RISK'
                      ? 'bg-status-review/10 border-status-review/30 text-status-review'
                      : 'bg-status-clear/10 border-status-clear/30 text-status-clear'
                }`}>
                  <span aria-hidden="true">{c.risk_level === 'HIGH_RISK' ? '⚑' : c.risk_level === 'MEDIUM_RISK' ? '⚠' : '✓'}</span>
                  {riskLabel(c.risk_level)}
                </span>
              )}
            </div>

            {/* Row 3: Officer + checkpoint + action */}
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent inline-block" />
                  {c.field_officer_username}
                </span>
                <span>·</span>
                <span>{checkpointName}</span>
                {c.assigned_officer_username && c.assigned_officer_username !== c.field_officer_username && (
                  <>
                    <span>·</span>
                    <span className="text-accent">Assigned: {c.assigned_officer_username}</span>
                  </>
                )}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); navigate(`/console/cases/${c.id}`) }}
                className="shrink-0 rounded border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-card group-hover:border-accent group-hover:text-accent transition-colors"
              >
                Review →
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
