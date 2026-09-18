import type { CaseStatus } from '../api/types'

// Design rule (CLAUDE.md): never rely on color alone — every status badge
// pairs a color with a distinct icon glyph and a text label, so it still
// reads correctly for colorblind users or in grayscale printouts.
const STATUS_CONFIG: Record<CaseStatus, { label: string; icon: string; className: string }> = {
  PENDING_SYNC: { label: 'Pending Sync', icon: '⟳', className: 'bg-secondary text-muted-foreground border-border' },
  PENDING: { label: 'Pending', icon: '○', className: 'bg-secondary text-muted-foreground border-border' },
  SENT: { label: 'Sent', icon: '➤', className: 'bg-chart-1/10 text-chart-1 border-chart-1/30' },
  REVIEW_REQUIRED: {
    label: 'Review Required',
    icon: '!',
    className: 'bg-status-review-bg text-status-review border-status-review/30',
  },
  CLEAR: { label: 'Clear', icon: '✓', className: 'bg-status-clear-bg text-status-clear border-status-clear/30' },
  SECONDARY_REVIEW: {
    label: 'Secondary Review',
    icon: '!',
    className: 'bg-status-review-bg text-status-review border-status-review/30',
  },
  HOLD_REFER: { label: 'Hold / Refer', icon: '✕', className: 'bg-status-high-bg text-status-high border-status-high/30' },
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  const config = STATUS_CONFIG[status] ?? { label: status, icon: '?', className: 'bg-secondary text-muted-foreground' }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${config.className}`}
    >
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  )
}

const PRIORITY_CONFIG: Record<string, { label: string; className: string }> = {
  LOW: { label: 'Low', className: 'bg-secondary text-muted-foreground' },
  MEDIUM: { label: 'Medium', className: 'bg-status-review-bg text-status-review' },
  HIGH: { label: 'High Priority', className: 'bg-status-high-bg text-status-high' },
}

export function PriorityBadge({ priority }: { priority: string }) {
  const config = PRIORITY_CONFIG[priority] ?? { label: priority, className: 'bg-secondary text-muted-foreground' }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}
