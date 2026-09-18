import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../lib/utils'

// MetricCard shape ported from sales-ops-dashboard/components/dashboard/metric-card.tsx:
// icon badge that recolors on hover, large value, optional icon, staggered
// mount-in animation via an index-driven delay.
export function StatTile({
  label,
  value,
  accent,
  icon: Icon,
  delay = 0,
}: {
  label: string
  value: string | number
  accent?: 'clear' | 'review' | 'high' | 'analytical' | 'default'
  icon?: LucideIcon
  delay?: number
}) {
  const accentClass =
    accent === 'clear'
      ? 'text-status-clear'
      : accent === 'review'
        ? 'text-status-review'
        : accent === 'high'
          ? 'text-status-high'
          : accent === 'analytical'
            ? 'text-analytical'
            : 'text-foreground'

  return (
    <div
      className="group relative animate-in fade-in slide-in-from-bottom-4 overflow-hidden rounded-xl border border-border bg-card p-5 duration-500 hover:border-accent/50"
      style={{ animationDelay: `${delay}ms`, animationFillMode: 'backwards' }}
    >
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="relative flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        {Icon && (
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary text-muted-foreground transition-colors group-hover:bg-accent/10 group-hover:text-accent">
            <Icon className="h-4.5 w-4.5" />
          </span>
        )}
      </div>
      <p className={cn('relative mt-2 text-2xl font-bold tracking-tight lg:text-3xl', accentClass)}>{value}</p>
    </div>
  )
}

export function Card({
  title,
  children,
  className = '',
}: {
  title?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-5', className)}>
      {title && <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>}
      {children}
    </div>
  )
}
