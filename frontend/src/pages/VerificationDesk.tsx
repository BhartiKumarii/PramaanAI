import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  Clock,
  CheckCircle2,
  Eye,
  RotateCcw,
  FileSearch,
  Search,
  ArrowUpDown,
  Inbox,
  ShieldAlert,
  ChevronDown,
} from 'lucide-react'
import { listCases, listAdminCheckpoints } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { StatusBadge, PriorityBadge } from '../components/StatusBadge'
import type { CaseListItem, CaseStatus, CasePriority } from '../api/types'

// ── Helpers ─────────────────────────────────────────────────────────────────

const DOC_TYPE_LABELS: Record<string, string> = {
  passport: 'Passport',
  visa: 'Visa',
  national_id: 'National ID',
  driving_licence: 'Driving Licence',
  driving_license: 'Driving Licence',
  permit: 'Permit',
  aadhaar: 'Aadhaar',
  pan_card: 'PAN Card',
  voter_id: 'Voter ID',
}

const STATUS_FILTER_OPTIONS: { label: string; value: CaseStatus | '' }[] = [
  { label: 'All Statuses', value: '' },
  { label: 'Awaiting Review', value: 'SENT' },
  { label: 'Flagged', value: 'REVIEW_REQUIRED' },
  { label: 'Verified', value: 'CLEAR' },
  { label: 'Re-capture', value: 'SECONDARY_REVIEW' },
  { label: 'Manual Review', value: 'HOLD_REFER' },
]

type SortMode = 'priority' | 'waiting' | 'newest'

const SORT_OPTIONS: { label: string; value: SortMode }[] = [
  { label: 'Priority', value: 'priority' },
  { label: 'Longest Waiting', value: 'waiting' },
  { label: 'Newest First', value: 'newest' },
]

function formatWaitingTime(dateStr: string | null): string {
  if (!dateStr) return '—'
  const ms = Date.now() - new Date(dateStr).getTime()
  if (ms < 0) return 'just now'
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  const remHours = hours % 24
  if (days < 7) return remHours > 0 ? `${days}d ${remHours}h` : `${days}d`
  return `${days}d`
}

function isOverdue(c: CaseListItem): boolean {
  if (c.status !== 'SENT' && c.status !== 'REVIEW_REQUIRED') return false
  const ts = c.sent_at ?? c.created_at
  return Date.now() - new Date(ts).getTime() > 24 * 60 * 60 * 1000
}

function humanizeRiskLevel(level: string | null): string {
  if (!level) return ''
  if (level === 'HIGH_RISK') return 'High Risk'
  if (level === 'MEDIUM_RISK') return 'Medium Risk'
  if (level === 'LOW_RISK') return 'Low Risk'
  return level.replace(/_/g, ' ')
}

function riskLevelColor(level: string | null): string {
  if (level === 'HIGH_RISK') return 'text-status-high'
  if (level === 'MEDIUM_RISK') return 'text-status-review'
  return 'text-status-clear'
}

// ── Stat card component ─────────────────────────────────────────────────────

function DeskStat({
  label,
  value,
  icon: Icon,
  accent,
  active,
  onClick,
}: {
  label: string
  value: number
  icon: typeof AlertTriangle
  accent?: 'clear' | 'review' | 'high' | 'default'
  active?: boolean
  onClick?: () => void
}) {
  const accentClass =
    accent === 'clear' ? 'text-status-clear' :
    accent === 'review' ? 'text-status-review' :
    accent === 'high' ? 'text-status-high' :
    'text-foreground'

  return (
    <button
      onClick={onClick}
      className={`group relative text-left w-full overflow-hidden rounded-xl border p-4 transition-all duration-200 ${
        active
          ? 'border-accent bg-accent/5 ring-1 ring-accent/30'
          : 'border-border bg-card hover:border-accent/40'
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
        <Icon className={`h-4 w-4 ${active ? 'text-accent' : 'text-muted-foreground'}`} />
      </div>
      <p className={`mt-1.5 text-2xl font-bold tracking-tight ${accentClass}`}>{value}</p>
    </button>
  )
}

// ── Main component ──────────────────────────────────────────────────────────

export function VerificationDesk() {
  const navigate = useNavigate()

  // Data — auto-refresh every 30s so sent cases appear without manual reload
  const [refreshTick, setRefreshTick] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => setRefreshTick(t => t + 1), 30_000)
    return () => clearInterval(interval)
  }, [])
  const allCases = useAsync(() => listCases({ limit: 200 }), [refreshTick])
  const checkpoints = useAsync(() => listAdminCheckpoints(), [])

  // Filters
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<CaseStatus | ''>('')
  const [priorityFilter, setPriorityFilter] = useState<CasePriority | ''>('')
  const [checkpointFilter, setCheckpointFilter] = useState('')
  const [docTypeFilter, setDocTypeFilter] = useState('')
  const [sortMode, setSortMode] = useState<SortMode>('priority')
  const [quickFilter, setQuickFilter] = useState<string | null>(null)

  // Computed stats
  const stats = useMemo(() => {
    const cases = allCases.data ?? []
    const awaitingReview = cases.filter(c => c.status === 'SENT' || c.status === 'REVIEW_REQUIRED').length
    const highPriority = cases.filter(c => c.priority === 'HIGH').length
    const recapture = cases.filter(c => c.status === 'SECONDARY_REVIEW').length
    const manualReview = cases.filter(c => c.status === 'HOLD_REFER').length
    const overdue = cases.filter(isOverdue).length
    return { awaitingReview, highPriority, recapture, manualReview, overdue }
  }, [allCases.data])

  // Unique document types for filter
  const docTypes = useMemo(() => {
    const types = new Set((allCases.data ?? []).map(c => c.document_type).filter(Boolean))
    return Array.from(types).sort()
  }, [allCases.data])

  // Filtered + sorted cases
  const visible = useMemo(() => {
    let items = allCases.data ?? []

    // Quick filter from stat cards
    if (quickFilter === 'awaiting') items = items.filter(c => c.status === 'SENT' || c.status === 'REVIEW_REQUIRED')
    else if (quickFilter === 'high') items = items.filter(c => c.priority === 'HIGH')
    else if (quickFilter === 'recapture') items = items.filter(c => c.status === 'SECONDARY_REVIEW')
    else if (quickFilter === 'manual') items = items.filter(c => c.status === 'HOLD_REFER')
    else if (quickFilter === 'overdue') items = items.filter(isOverdue)

    // Standard filters
    if (statusFilter) items = items.filter(c => c.status === statusFilter)
    if (priorityFilter) items = items.filter(c => c.priority === priorityFilter)
    if (checkpointFilter) items = items.filter(c => c.checkpoint_code === checkpointFilter)
    if (docTypeFilter) items = items.filter(c => c.document_type === docTypeFilter)

    // Search
    const q = search.trim().toLowerCase()
    if (q) {
      items = items.filter(c =>
        c.case_number.toLowerCase().includes(q) ||
        (c.traveler_name ?? '').toLowerCase().includes(q) ||
        (c.nationality ?? '').toLowerCase().includes(q) ||
        (c.document_type ?? '').toLowerCase().includes(q) ||
        c.field_officer_username.toLowerCase().includes(q) ||
        c.checkpoint_code.toLowerCase().includes(q)
      )
    }

    // Sort
    items = [...items].sort((a, b) => {
      if (sortMode === 'priority') {
        const pri: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 }
        const diff = (pri[a.priority] ?? 2) - (pri[b.priority] ?? 2)
        if (diff !== 0) return diff
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      }
      if (sortMode === 'waiting') {
        const ta = new Date(a.sent_at ?? a.created_at).getTime()
        const tb = new Date(b.sent_at ?? b.created_at).getTime()
        return ta - tb
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

    return items
  }, [allCases.data, search, statusFilter, priorityFilter, checkpointFilter, docTypeFilter, sortMode, quickFilter])

  function toggleQuickFilter(key: string) {
    setQuickFilter(prev => prev === key ? null : key)
  }

  const uniqueCheckpoints = useMemo(() => {
    const cp = checkpoints.data ?? []
    return cp.map(c => c.code).sort()
  }, [checkpoints.data])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Verification Desk</h1>
        <p className="text-sm text-muted-foreground">
          All cases requiring review, decision, or action — your operational workspace.
        </p>
      </div>

      {/* Stat cards */}
      {allCases.loading ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} className="h-[88px] animate-pulse rounded-xl border border-border bg-secondary" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <DeskStat
            label="Awaiting Review"
            value={stats.awaitingReview}
            icon={Inbox}
            accent="review"
            active={quickFilter === 'awaiting'}
            onClick={() => toggleQuickFilter('awaiting')}
          />
          <DeskStat
            label="High Priority"
            value={stats.highPriority}
            icon={AlertTriangle}
            accent="high"
            active={quickFilter === 'high'}
            onClick={() => toggleQuickFilter('high')}
          />
          <DeskStat
            label="Re-capture Required"
            value={stats.recapture}
            icon={RotateCcw}
            accent="review"
            active={quickFilter === 'recapture'}
            onClick={() => toggleQuickFilter('recapture')}
          />
          <DeskStat
            label="Manual Review"
            value={stats.manualReview}
            icon={FileSearch}
            accent="high"
            active={quickFilter === 'manual'}
            onClick={() => toggleQuickFilter('manual')}
          />
          <DeskStat
            label="Overdue (>24h)"
            value={stats.overdue}
            icon={Clock}
            accent={stats.overdue > 0 ? 'high' : 'default'}
            active={quickFilter === 'overdue'}
            onClick={() => toggleQuickFilter('overdue')}
          />
        </div>
      )}

      {/* Overdue warning banner */}
      {stats.overdue > 0 && !quickFilter && (
        <button
          onClick={() => toggleQuickFilter('overdue')}
          className="flex w-full items-center justify-between rounded-lg border border-status-high/30 bg-status-high-bg px-4 py-3 text-left transition-colors hover:border-status-high/50"
        >
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="h-4 w-4 text-status-high shrink-0" />
            <div>
              <p className="text-sm font-semibold text-status-high">
                {stats.overdue} case{stats.overdue !== 1 ? 's' : ''} overdue
              </p>
              <p className="text-xs text-muted-foreground">
                Waiting longer than 24 hours without a decision
              </p>
            </div>
          </div>
          <span className="text-xs font-medium text-status-high">View overdue →</span>
        </button>
      )}

      {/* Search + Filters bar */}
      <div className="flex flex-wrap items-end gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search case, name, checkpoint…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full rounded-lg border border-border bg-background pl-9 pr-8 py-2 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
            >
              ✕
            </button>
          )}
        </div>

        {/* Status filter */}
        <div className="relative">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value as CaseStatus | '')}
            className="appearance-none rounded-lg border border-border bg-background px-3 py-2 pr-8 text-sm text-foreground focus:border-ring focus:outline-none"
          >
            {STATUS_FILTER_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        </div>

        {/* Priority filter */}
        <div className="flex gap-1">
          {(['', 'HIGH', 'MEDIUM', 'LOW'] as const).map(p => (
            <button
              key={p}
              onClick={() => setPriorityFilter(p as CasePriority | '')}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                priorityFilter === p
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-muted-foreground hover:bg-card'
              }`}
            >
              {p === '' ? 'All' : p === 'HIGH' ? 'High' : p === 'MEDIUM' ? 'Medium' : 'Low'}
            </button>
          ))}
        </div>

        {/* Checkpoint filter */}
        {uniqueCheckpoints.length > 0 && (
          <div className="relative">
            <select
              value={checkpointFilter}
              onChange={e => setCheckpointFilter(e.target.value)}
              className="appearance-none rounded-lg border border-border bg-background px-3 py-2 pr-8 text-sm text-foreground focus:border-ring focus:outline-none"
            >
              <option value="">All Checkpoints</option>
              {uniqueCheckpoints.map(cp => (
                <option key={cp} value={cp}>{cp}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          </div>
        )}

        {/* Document type filter */}
        {docTypes.length > 0 && (
          <div className="relative">
            <select
              value={docTypeFilter}
              onChange={e => setDocTypeFilter(e.target.value)}
              className="appearance-none rounded-lg border border-border bg-background px-3 py-2 pr-8 text-sm text-foreground focus:border-ring focus:outline-none"
            >
              <option value="">All Documents</option>
              {docTypes.map(dt => (
                <option key={dt} value={dt}>{DOC_TYPE_LABELS[dt] ?? dt}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          </div>
        )}

        {/* Sort */}
        <div className="flex items-center gap-1.5">
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
          {SORT_OPTIONS.map(s => (
            <button
              key={s.value}
              onClick={() => setSortMode(s.value)}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                sortMode === s.value
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-muted-foreground hover:bg-card'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active filter indicator */}
      {(quickFilter || statusFilter || priorityFilter || checkpointFilter || docTypeFilter || search) && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{visible.length} case{visible.length !== 1 ? 's' : ''} matching filters</span>
          <button
            onClick={() => {
              setQuickFilter(null)
              setStatusFilter('')
              setPriorityFilter('')
              setCheckpointFilter('')
              setDocTypeFilter('')
              setSearch('')
            }}
            className="text-accent hover:underline"
          >
            Clear all filters
          </button>
        </div>
      )}

      {/* Loading */}
      {allCases.loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-accent" />
        </div>
      )}

      {/* Error */}
      {allCases.error && (
        <div className="rounded-lg border border-status-high/30 bg-status-high-bg px-4 py-6 text-center">
          <p className="text-sm text-status-high">{allCases.error}</p>
          <button
            onClick={() => allCases.refetch()}
            className="mt-3 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent/90"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!allCases.loading && !allCases.error && visible.length === 0 && (
        <div className="rounded-xl border border-border bg-card py-16 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-muted-foreground/30" />
          <p className="mt-3 text-sm font-medium text-foreground">
            {search || statusFilter || priorityFilter || checkpointFilter || docTypeFilter || quickFilter
              ? 'No cases match these filters.'
              : 'No cases yet.'}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {search || quickFilter ? 'Try adjusting your search or filters.' : 'Cases will appear here when officers submit screenings from the field.'}
          </p>
        </div>
      )}

      {/* Cases table */}
      {!allCases.loading && !allCases.error && visible.length > 0 && (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/40">
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Case ID</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Person</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Document</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Checkpoint</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Priority</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Status / Risk</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Waiting</th>
                  <th className="whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Assigned</th>
                  <th className="whitespace-nowrap px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Action</th>
                </tr>
              </thead>
              <tbody>
                {visible.map(c => {
                  const overdueCase = isOverdue(c)
                  return (
                    <tr
                      key={c.id}
                      onClick={() => navigate(`/console/cases/${c.id}`)}
                      className={`group cursor-pointer border-b border-border/50 transition-colors hover:bg-accent/5 ${
                        overdueCase ? 'bg-status-high/[0.02]' : ''
                      }`}
                    >
                      {/* Case ID */}
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="font-mono text-xs font-medium text-foreground">
                          {c.case_number}
                        </span>
                      </td>

                      {/* Person */}
                      <td className="px-4 py-3">
                        <p className="text-sm font-medium text-foreground truncate max-w-[160px]">
                          {c.traveler_name || '—'}
                        </p>
                        {c.nationality && (
                          <p className="text-[11px] text-muted-foreground">{c.nationality}</p>
                        )}
                      </td>

                      {/* Document */}
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="text-xs text-foreground">
                          {DOC_TYPE_LABELS[c.document_type?.toLowerCase() ?? ''] ?? c.document_type ?? '—'}
                        </span>
                      </td>

                      {/* Checkpoint */}
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="rounded bg-secondary px-2 py-0.5 text-xs font-medium text-foreground border border-border">
                          {c.checkpoint_code}
                        </span>
                      </td>

                      {/* Priority */}
                      <td className="whitespace-nowrap px-4 py-3">
                        <PriorityBadge priority={c.priority} />
                      </td>

                      {/* Status / Risk */}
                      <td className="px-4 py-3">
                        <StatusBadge status={c.status} />
                        {c.risk_level && (
                          <p className={`mt-1 text-[11px] font-medium ${riskLevelColor(c.risk_level)}`}>
                            {humanizeRiskLevel(c.risk_level)}
                            {c.risk_score != null && (
                              <span className="ml-1 opacity-60">({Math.round(c.risk_score)}%)</span>
                            )}
                          </p>
                        )}
                      </td>

                      {/* Waiting time */}
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`text-xs font-medium ${overdueCase ? 'text-status-high' : 'text-muted-foreground'}`}>
                          {overdueCase && <span className="mr-1">⚠</span>}
                          {formatWaitingTime(c.sent_at ?? c.created_at)}
                        </span>
                      </td>

                      {/* Assigned */}
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="text-xs text-muted-foreground">
                          {c.assigned_officer_username ?? (
                            <span className="italic opacity-50">Unassigned</span>
                          )}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        <button
                          onClick={e => { e.stopPropagation(); navigate(`/console/cases/${c.id}`) }}
                          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent/10 hover:border-accent/40 hover:text-accent"
                        >
                          <Eye className="h-3 w-3" />
                          Review
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Table footer */}
          <div className="border-t border-border px-4 py-2.5 text-xs text-muted-foreground flex items-center justify-between">
            <span>
              Showing {visible.length} of {(allCases.data ?? []).length} cases
            </span>
            <button
              onClick={() => allCases.refetch()}
              className="flex items-center gap-1 text-accent hover:underline"
            >
              <RotateCcw className="h-3 w-3" />
              Refresh
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
