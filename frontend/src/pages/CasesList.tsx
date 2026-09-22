import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listCases } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { CaseTable } from '../components/CaseTable'
import { Card } from '../components/StatTile'
import type { CaseListItem, CaseStatus } from '../api/types'

// ── Status filter config ─────────────────────────────────────────────────────

const STATUS_FILTERS: { label: string; value: CaseStatus | '' }[] = [
  { label: 'All', value: '' },
  { label: 'Submitted for Review', value: 'SENT' },
  { label: 'Flagged for Review', value: 'REVIEW_REQUIRED' },
  { label: 'Verified', value: 'CLEAR' },
  { label: 'Re-capture Required', value: 'SECONDARY_REVIEW' },
  { label: 'Manual Verification', value: 'HOLD_REFER' },
]

const ALERT_STATUSES: CaseStatus[] = ['REVIEW_REQUIRED']
const REQUEST_STATUSES: CaseStatus[] = ['PENDING_SYNC', 'PENDING', 'SENT']
const RESULT_STATUSES: CaseStatus[] = ['CLEAR', 'SECONDARY_REVIEW', 'HOLD_REFER']

type View = 'all' | 'alerts' | 'requests' | 'results'

interface ViewConfig {
  title: string
  subtitle: string
  statuses?: CaseStatus[]
  showSentAt?: boolean
  emptyMessage?: string
}

const VIEW_CONFIG: Record<View, ViewConfig> = {
  all: {
    title: 'All Cases',
    subtitle: 'Every case across all checkpoints.',
  },
  alerts: {
    title: 'Needs Attention',
    subtitle: 'Cases flagged for review or referred for manual verification — action required.',
    statuses: ALERT_STATUSES,
    emptyMessage: 'No cases currently need attention.',
  },
  requests: {
    title: 'Pending Review',
    subtitle: 'Cases submitted by field officers — awaiting an admin verification decision.',
    statuses: REQUEST_STATUSES,
    showSentAt: true,
    emptyMessage: 'No cases are currently waiting for review.',
  },
  results: {
    title: 'Decided Cases',
    subtitle: 'Cases where a verification decision has been recorded.',
    statuses: RESULT_STATUSES,
    emptyMessage: 'No decisions have been recorded yet.',
  },
}

// ── Priority filter ──────────────────────────────────────────────────────────

const PRIORITY_FILTERS = [
  { label: 'All priorities', value: '' },
  { label: 'High', value: 'HIGH' },
  { label: 'Medium', value: 'MEDIUM' },
  { label: 'Low', value: 'LOW' },
]

// ── Summary row ──────────────────────────────────────────────────────────────

function ViewSummary({ cases, view }: { cases: CaseListItem[]; view: View }) {
  if (view === 'requests') {
    const stale = cases.filter((c) => {
      if (!c.sent_at) return false
      return Date.now() - new Date(c.sent_at).getTime() > 24 * 60 * 60 * 1000
    })
    const sent = cases.filter((c) => c.status === 'SENT').length
    const flagged = cases.filter((c) => c.status === 'REVIEW_REQUIRED').length
    return (
      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span><span className="font-semibold text-foreground">{cases.length}</span> total</span>
        <span><span className="font-semibold text-chart-1">{sent}</span> submitted</span>
        <span><span className="font-semibold text-status-review">{flagged}</span> flagged</span>
        {stale.length > 0 && (
          <span className="text-status-high font-medium">
            ⚠ {stale.length} waiting &gt;24h
          </span>
        )}
      </div>
    )
  }
  if (view === 'alerts') {
    const high = cases.filter((c) => c.priority === 'HIGH').length
    return (
      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span><span className="font-semibold text-foreground">{cases.length}</span> flagged for review</span>
        {high > 0 && <span><span className="font-semibold text-status-high">{high}</span> high priority</span>}
      </div>
    )
  }
  if (view === 'results') {
    const verified = cases.filter((c) => c.status === 'CLEAR').length
    const recapture = cases.filter((c) => c.status === 'SECONDARY_REVIEW').length
    const manual = cases.filter((c) => c.status === 'HOLD_REFER').length
    return (
      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span><span className="font-semibold text-foreground">{cases.length}</span> total</span>
        <span><span className="font-semibold text-status-clear">{verified}</span> verified</span>
        <span><span className="font-semibold text-status-review">{recapture}</span> re-capture</span>
        <span><span className="font-semibold text-status-high">{manual}</span> manual</span>
      </div>
    )
  }
  return (
    <div className="text-sm text-muted-foreground">
      <span className="font-semibold text-foreground">{cases.length}</span> cases
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export function CasesList({ view = 'all' }: { view?: View }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const statusFilter = (searchParams.get('status') as CaseStatus | null) ?? ''
  const [search, setSearch] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')

  const config = VIEW_CONFIG[view]

  const allCases = useAsync(
    () => listCases({ limit: 200 }),
    [view],
  )

  const visible = useMemo(() => {
    let items = allCases.data ?? []

    // View-level status filter
    if (config.statuses) {
      items = items.filter((c) => config.statuses!.includes(c.status))
    }

    // Status chip filter (only "all" view)
    if (!config.statuses && statusFilter) {
      items = items.filter((c) => c.status === statusFilter)
    }

    // Priority filter
    if (priorityFilter) {
      items = items.filter((c) => c.priority === priorityFilter)
    }

    // Search (client-side): match case_number, traveler_name, nationality, document_type
    const q = search.trim().toLowerCase()
    if (q) {
      items = items.filter(
        (c) =>
          c.case_number.toLowerCase().includes(q) ||
          (c.traveler_name ?? '').toLowerCase().includes(q) ||
          (c.nationality ?? '').toLowerCase().includes(q) ||
          (c.document_type ?? '').toLowerCase().includes(q) ||
          c.field_officer_username.toLowerCase().includes(q) ||
          c.checkpoint_code.toLowerCase().includes(q),
      )
    }

    // Sort: requests view → oldest sent_at first (most urgent); alerts → high priority first
    if (view === 'requests') {
      items = [...items].sort((a, b) => {
        const ta = a.sent_at ? new Date(a.sent_at).getTime() : new Date(a.created_at).getTime()
        const tb = b.sent_at ? new Date(b.sent_at).getTime() : new Date(b.created_at).getTime()
        return ta - tb // oldest first = most urgent
      })
    } else if (view === 'alerts') {
      const pri: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 }
      items = [...items].sort((a, b) => (pri[a.priority] ?? 2) - (pri[b.priority] ?? 2))
    } else {
      // Default: newest first
      items = [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    }

    return items
  }, [allCases.data, config.statuses, statusFilter, priorityFilter, search, view])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">{config.title}</h1>
        <p className="text-sm text-muted-foreground">{config.subtitle}</p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <input
            type="text"
            placeholder="Search case, name, checkpoint…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none"
          />
          {search && (
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
              onClick={() => setSearch('')}
            >
              ✕
            </button>
          )}
        </div>

        {/* Priority filter */}
        <div className="flex gap-1">
          {PRIORITY_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setPriorityFilter(f.value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                priorityFilter === f.value
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-muted-foreground hover:bg-card'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Status chips — only in "all" view */}
        {view === 'all' && (
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.label}
                onClick={() => setSearchParams(f.value ? { status: f.value } : {})}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
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
      </div>

      {/* Results count / summary */}
      {!allCases.loading && !allCases.error && visible.length > 0 && (
        <ViewSummary cases={visible} view={view} />
      )}

      {/* Table */}
      <Card>
        {allCases.loading && <p className="py-6 text-sm text-muted-foreground">Loading…</p>}
        {allCases.error && <p className="text-sm text-status-high">{allCases.error}</p>}
        {!allCases.loading && !allCases.error && visible.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {search || priorityFilter ? 'No cases match these filters.' : (config.emptyMessage ?? 'No cases found.')}
          </p>
        )}
        {!allCases.loading && !allCases.error && visible.length > 0 && (
          <CaseTable cases={visible} showSentAt={config.showSentAt} />
        )}
      </Card>
    </div>
  )
}
