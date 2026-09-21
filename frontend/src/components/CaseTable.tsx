import { useNavigate } from 'react-router-dom'
import type { CaseListItem } from '../api/types'
import { StatusBadge, PriorityBadge } from './StatusBadge'

function ageLabel(isoDate: string | null): string {
  if (!isoDate) return '—'
  const ms = Date.now() - new Date(isoDate).getTime()
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function isStale(isoDate: string | null): boolean {
  if (!isoDate) return false
  return Date.now() - new Date(isoDate).getTime() > 24 * 60 * 60 * 1000
}

const DOC_LABELS: Record<string, string> = {
  passport: 'Passport',
  national_id: 'National ID',
  visa: 'Visa',
  driving_licence: 'Licence',
  driving_license: 'Licence',
  aadhaar: 'Aadhaar',
  pan_card: 'PAN',
  voter_id: 'Voter ID',
  citizenship_certificate: 'Citizenship',
  permit: 'Permit',
}

export function CaseTable({ cases, showSentAt = false }: { cases: CaseListItem[]; showSentAt?: boolean }) {
  const navigate = useNavigate()

  if (cases.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No cases match the current filters.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[800px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-4">Case</th>
            <th className="py-2 pr-4">Document</th>
            <th className="py-2 pr-4">Officer · Checkpoint</th>
            <th className="py-2 pr-4">{showSentAt ? 'Waiting' : 'Submitted'}</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Priority</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => {
            const stale = showSentAt ? isStale(c.sent_at) : false
            const docLabel = DOC_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type
            return (
              <tr
                key={c.id}
                className={`border-b border-border hover:bg-secondary cursor-pointer ${stale ? 'bg-status-high-bg/30' : ''}`}
                onClick={() => navigate(`/console/cases/${c.id}`)}
              >
                <td className="py-2.5 pr-4">
                  <p className="font-medium text-foreground">{c.case_number}</p>
                  {c.traveler_name && (
                    <p className="mt-0.5 text-xs text-muted-foreground">{c.traveler_name}</p>
                  )}
                  {c.nationality && (
                    <p className="text-xs text-muted-foreground">{c.nationality}</p>
                  )}
                </td>
                <td className="py-2.5 pr-4 text-muted-foreground">
                  {docLabel || '—'}
                </td>
                <td className="py-2.5 pr-4">
                  <p className="text-muted-foreground">{c.field_officer_username}</p>
                  <p className="text-xs text-muted-foreground">{c.checkpoint_code}</p>
                </td>
                <td className="py-2.5 pr-4">
                  {showSentAt ? (
                    <span className={`text-xs font-medium ${stale ? 'text-status-high' : 'text-muted-foreground'}`}>
                      {ageLabel(c.sent_at)}
                      {stale && <span className="ml-1 text-status-high">⚠</span>}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {new Date(c.created_at).toLocaleDateString()}{' '}
                      <span className="text-muted-foreground/60">{new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </span>
                  )}
                </td>
                <td className="py-2.5 pr-4">
                  <StatusBadge status={c.status} />
                </td>
                <td className="py-2.5 pr-4">
                  <PriorityBadge priority={c.priority} />
                </td>
                <td className="py-2.5">
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/console/cases/${c.id}`) }}
                    className="rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-card whitespace-nowrap"
                  >
                    Review →
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
