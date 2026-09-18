import { useNavigate } from 'react-router-dom'
import type { CaseListItem } from '../api/types'
import { StatusBadge, PriorityBadge } from './StatusBadge'

export function CaseTable({ cases }: { cases: CaseListItem[] }) {
  const navigate = useNavigate()

  if (cases.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No cases match the current filters.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
            <th className="py-2 pr-4">Case ID</th>
            <th className="py-2 pr-4">Source Officer</th>
            <th className="py-2 pr-4">Checkpoint</th>
            <th className="py-2 pr-4">Time</th>
            <th className="py-2 pr-4">Result</th>
            <th className="py-2 pr-4">Priority</th>
            <th className="py-2 pr-4"></th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.id} className="border-b border-border hover:bg-secondary">
              <td className="py-2.5 pr-4 font-medium text-foreground">{c.case_number}</td>
              <td className="py-2.5 pr-4 text-muted-foreground">{c.field_officer_username}</td>
              <td className="py-2.5 pr-4 text-muted-foreground">{c.checkpoint_code}</td>
              <td className="py-2.5 pr-4 text-muted-foreground">{new Date(c.created_at).toLocaleString()}</td>
              <td className="py-2.5 pr-4">
                <StatusBadge status={c.status} />
              </td>
              <td className="py-2.5 pr-4">
                <PriorityBadge priority={c.priority} />
              </td>
              <td className="py-2.5 pr-4">
                <button
                  onClick={() => navigate(`/console/cases/${c.id}`)}
                  className="rounded border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-card"
                >
                  Open Case
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
