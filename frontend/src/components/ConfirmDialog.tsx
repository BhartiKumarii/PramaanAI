export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  requireReason,
  onCancel,
  onConfirm,
}: {
  title: string
  description: string
  confirmLabel: string
  requireReason: boolean
  onCancel: () => void
  onConfirm: (reason: string) => void
}) {
  let reason = ''
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-lg bg-card p-6 shadow-xl">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        {requireReason && (
          <textarea
            className="mt-3 w-full rounded-md border border-border p-2 text-sm focus:border-ring focus:outline-none"
            rows={3}
            placeholder="Reason (required)"
            onChange={(e) => {
              reason = e.target.value
            }}
          />
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-secondary"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
