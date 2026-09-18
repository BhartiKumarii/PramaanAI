import { useSearchParams } from 'react-router-dom'
import { listCases } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { CaseTable } from '../components/CaseTable'
import { Card } from '../components/StatTile'
import type { CaseStatus } from '../api/types'

const STATUS_FILTERS: { label: string; value: CaseStatus | '' }[] = [
  { label: 'All', value: '' },
  { label: 'Sent', value: 'SENT' },
  { label: 'Review Required', value: 'REVIEW_REQUIRED' },
  { label: 'Clear', value: 'CLEAR' },
  { label: 'Secondary Review', value: 'SECONDARY_REVIEW' },
  { label: 'Hold / Refer', value: 'HOLD_REFER' },
]

const ALERT_STATUSES: CaseStatus[] = ['REVIEW_REQUIRED', 'SECONDARY_REVIEW', 'HOLD_REFER']
// "Screening Requests" — hasn't reached a recorded officer decision yet.
const REQUEST_STATUSES: CaseStatus[] = ['PENDING_SYNC', 'PENDING', 'SENT', 'REVIEW_REQUIRED']
// "Screening Results" — a decision has actually been recorded (POST
// /cases/{id}/decision), matching Case's own "Terminal states" comment.
const RESULT_STATUSES: CaseStatus[] = ['CLEAR', 'SECONDARY_REVIEW', 'HOLD_REFER']

type View = 'all' | 'alerts' | 'requests' | 'results'

const VIEW_CONFIG: Record<View, { title: string; subtitle: string; statuses?: CaseStatus[] }> = {
  all: { title: 'Cases', subtitle: 'Cases scoped to your role and checkpoint.' },
  alerts: {
    title: 'Alerts & Review',
    subtitle: 'Cases flagged for review, secondary review, or hold/refer.',
    statuses: ALERT_STATUSES,
  },
  requests: {
    title: 'Screening Requests',
    subtitle: "Cases that haven't reached a recorded officer decision yet.",
    statuses: REQUEST_STATUSES,
  },
  results: {
    title: 'Screening Results',
    subtitle: 'Cases with a recorded officer decision — clear, secondary review, or hold/refer.',
    statuses: RESULT_STATUSES,
  },
}

export function CasesList({ view = 'all' }: { view?: View }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const statusFilter = (searchParams.get('status') as CaseStatus | null) ?? ''
  const config = VIEW_CONFIG[view]

  const cases = useAsync(() => {
    if (config.statuses) return listCases({ limit: 100 })
    return listCases(statusFilter ? { status_filter: statusFilter, limit: 100 } : { limit: 100 })
  }, [statusFilter, view])

  const visibleCases = config.statuses ? cases.data?.filter((c) => config.statuses!.includes(c.status)) : cases.data

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">{config.title}</h1>
        <p className="text-sm text-muted-foreground">{config.subtitle}</p>
      </div>

      {view === 'all' && (
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => setSearchParams(f.value ? { status: f.value } : {})}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                statusFilter === f.value
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-muted-foreground hover:bg-card'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      <Card>
        {cases.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {cases.error && <p className="text-sm text-status-high">{cases.error}</p>}
        {visibleCases && <CaseTable cases={visibleCases} />}
      </Card>
    </div>
  )
}
