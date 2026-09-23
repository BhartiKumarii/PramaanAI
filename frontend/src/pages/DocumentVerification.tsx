import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileImage,
  History,
  Info,
  Loader2,
  ScanSearch,
  ShieldCheck,
  Upload,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import {
  getDocumentVerification,
  listDocumentVerifications,
  recordOfficerAction,
  verifyDocuments,
  type CheckStatus,
  type Evidence,
  type OfficerAction,
  type VerificationListItem,
  type VerificationOutcome,
} from '../api/docverify'
import { cn } from '../lib/utils'

// Plain-language status presentation. Colour is never the only signal:
// every status carries an icon and a text label (CLAUDE.md design rule).
const STATUS_UI: Record<CheckStatus, { label: string; icon: LucideIcon; cls: string }> = {
  PASS: { label: 'Verified', icon: CheckCircle2, cls: 'text-status-clear bg-status-clear-bg border-status-clear/30' },
  REVIEW_REQUIRED: { label: 'Review required', icon: AlertTriangle, cls: 'text-status-review bg-status-review-bg border-status-review/30' },
  FAIL: { label: 'Check failed — review', icon: XCircle, cls: 'text-status-high bg-status-high-bg border-status-high/30' },
  NOT_VERIFIED: { label: 'Not verified', icon: Info, cls: 'text-muted-foreground bg-secondary border-border' },
  REGISTRY_NOT_AVAILABLE: { label: 'Registry not available', icon: Info, cls: 'text-chart-1 bg-chart-1/10 border-chart-1/30' },
  OFFICIAL_VERIFICATION_REQUIRED: { label: 'Official verification required', icon: Info, cls: 'text-chart-1 bg-chart-1/10 border-chart-1/30' },
  REFERENCE_NOT_AVAILABLE: { label: 'No reference available', icon: Info, cls: 'text-muted-foreground bg-secondary border-border' },
  NOT_APPLICABLE: { label: 'Not applicable', icon: Info, cls: 'text-muted-foreground bg-secondary border-border' },
}

const LINE_ICON = { ok: CheckCircle2, warn: AlertTriangle, info: Info, fail: XCircle }
const LINE_CLS = { ok: 'text-status-clear', warn: 'text-status-review', info: 'text-chart-1', fail: 'text-status-high' }

const BOX_COLOUR: Record<string, string> = {
  stamp_detection: '#f97316', stamp_forensics: '#ef4444', tampering_analysis: '#ef4444', photo: '#22c55e',
  face_verification: '#22c55e', mrz: '#3b82f6', mrz_structure: '#3b82f6', machine_readable_code: '#a855f7',
  yellow_gold_feature: '#eab308', layout: '#64748b', security_features: '#14b8a6',
}

const ACTIONS: { value: OfficerAction; label: string; needsReason: boolean }[] = [
  { value: 'CLEARED', label: 'Clear', needsReason: false },
  { value: 'REFERRED_FOR_SECONDARY_INSPECTION', label: 'Refer for secondary inspection', needsReason: true },
  { value: 'RECAPTURE_REQUESTED', label: 'Request recapture', needsReason: true },
  { value: 'OFFICIAL_VERIFICATION_REQUESTED', label: 'Request official verification', needsReason: true },
]

function humanize(s: string | null | undefined) {
  return (s ?? '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
}

function StatusPill({ status }: { status: CheckStatus }) {
  const ui = STATUS_UI[status] ?? STATUS_UI.NOT_VERIFIED
  const Icon = ui.icon
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium', ui.cls)}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {ui.label}
    </span>
  )
}

function EvidenceViewer({
  src,
  size,
  evidence,
  activeIds,
}: {
  src: string | null
  size: number[] | null
  evidence: Evidence[]
  activeIds: Set<string>
}) {
  if (!src) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
        The document image is not stored on the server. Evidence regions can only be highlighted in the session that
        captured the image.
      </div>
    )
  }
  const [w, h] = size ?? [1, 1]
  const shown = evidence.filter((e) => e.bbox && (activeIds.size === 0 || activeIds.has(e.id)))
  return (
    <div className="relative w-full overflow-hidden rounded-lg border border-border bg-black/40">
      <img src={src} alt="Submitted document" className="block w-full" />
      <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        {shown.map((e) => {
          const [x0, y0, x1, y1] = e.bbox as number[]
          const colour = BOX_COLOUR[e.check] ?? '#38bdf8'
          return (
            <g key={e.id}>
              <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill={`${colour}22`} stroke={colour}
                strokeWidth={Math.max(2, w / 400)} />
              <text x={x0 + 4} y={Math.max(14, y0 - 4)} fill={colour} fontSize={Math.max(12, w / 60)} fontWeight={600}>
                {humanize(e.check)}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export function DocumentVerification() {
  const [files, setFiles] = useState<File[]>([])
  const [liveFace, setLiveFace] = useState<File | null>(null)
  const [route, setRoute] = useState('')
  const [direction, setDirection] = useState('')
  const [nationality, setNationality] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<VerificationOutcome | null>(null)
  // Object URLs for the selected files: derived, and revoked when replaced.
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files])
  const [tab, setTab] = useState<'evidence' | 'data' | 'document' | 'history'>('evidence')
  const [docIndex, setDocIndex] = useState(0)
  const [activeCheck, setActiveCheck] = useState<string | null>(null)
  const [history, setHistory] = useState<VerificationListItem[]>([])
  const [actionReason, setActionReason] = useState('')
  const [actionDone, setActionDone] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews])

  useEffect(() => {
    if (tab === 'history') listDocumentVerifications().then(setHistory).catch(() => setHistory([]))
  }, [tab, result])

  const run = async () => {
    if (!files.length) return
    setBusy(true)
    setError(null)
    setResult(null)
    setActionDone(null)
    try {
      const out = await verifyDocuments({
        files,
        liveFace,
        borderRoute: route || undefined,
        direction: direction || undefined,
        declaredNationality: nationality || undefined,
      })
      setResult(out)
      setDocIndex(0)
      setTab('evidence')
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Verification could not be completed. Check the connection and try again.')
    } finally {
      setBusy(false)
    }
  }

  const openStored = async (id: string) => {
    const env = await getDocumentVerification(id)
    setResult(env.result)
    setFiles([])
    setDocIndex(0)
    setTab('evidence')
  }

  const doc = result?.documents[docIndex]
  const activeIds = useMemo(() => {
    if (!result || !activeCheck) return new Set<string>()
    return new Set(result.check_details.filter((c) => c.name === activeCheck).flatMap((c) => c.evidence_ids))
  }, [result, activeCheck])
  const docEvidence = useMemo(
    () => (result ? result.evidence.filter((e) => e.document_index === docIndex) : []),
    [result, docIndex],
  )

  const submitAction = async (a: (typeof ACTIONS)[number]) => {
    if (!result?.id) return
    if (a.needsReason && !actionReason.trim()) {
      setActionDone('Please enter a reason for this action.')
      return
    }
    await recordOfficerAction(result.id, a.value, actionReason.trim() || undefined)
    setActionDone(`Recorded: ${a.label}`)
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Document Verification</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Evidence-based checks for passports, visas, permits, licences and stamps. The officer makes the final decision.
          </p>
        </div>
        <span className="rounded-full border border-border bg-secondary px-3 py-1 text-xs text-muted-foreground">
          Registry checks use fictional demo data
        </span>
      </header>

      <section className="rounded-xl border border-border bg-card p-5">
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
            className="flex min-h-40 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border p-6 text-center hover:border-accent"
          >
            <Upload className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">
              {files.length ? `${files.length} document image(s) selected` : 'Select 1–4 document images'}
            </p>
            <p className="text-xs text-muted-foreground">Passport page, visa, permit, licence, ID card or stamp page · JPEG/PNG/WEBP · max 10 MB</p>
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              className="hidden"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 4))}
            />
          </div>
          <div className="grid gap-3 text-sm">
            <label className="grid gap-1">
              <span className="text-xs text-muted-foreground">Border</span>
              <select value={route} onChange={(e) => setRoute(e.target.value)} className="rounded-md border border-border bg-input px-3 py-2">
                <option value="">Not specified</option>
                <option value="INDIA_NEPAL">India–Nepal</option>
                <option value="INDIA_BHUTAN">India–Bhutan</option>
              </select>
            </label>
            <label className="grid gap-1">
              <span className="text-xs text-muted-foreground">Direction</span>
              <select value={direction} onChange={(e) => setDirection(e.target.value)} className="rounded-md border border-border bg-input px-3 py-2">
                <option value="">Not specified</option>
                {route === 'INDIA_BHUTAN' ? (
                  <>
                    <option value="INDIA_TO_BHUTAN">India → Bhutan</option>
                    <option value="BHUTAN_TO_INDIA">Bhutan → India</option>
                  </>
                ) : (
                  <>
                    <option value="INDIA_TO_NEPAL">India → Nepal</option>
                    <option value="NEPAL_TO_INDIA">Nepal → India</option>
                  </>
                )}
              </select>
            </label>
            <label className="grid gap-1">
              <span className="text-xs text-muted-foreground">Declared nationality (optional)</span>
              <input value={nationality} onChange={(e) => setNationality(e.target.value)} placeholder="e.g. INDIAN"
                className="rounded-md border border-border bg-input px-3 py-2" />
            </label>
            <label className="grid gap-1">
              <span className="text-xs text-muted-foreground">Photo of the person presented (optional, for face comparison)</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setLiveFace(e.target.files?.[0] ?? null)}
                className="text-xs file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-foreground" />
            </label>
            <button
              type="button"
              disabled={!files.length || busy}
              onClick={run}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 font-medium text-accent-foreground disabled:opacity-40"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
              {busy ? 'Verifying…' : 'Run verification'}
            </button>
          </div>
        </div>
        {error && (
          <p role="alert" className="mt-4 flex items-center gap-2 rounded-md border border-status-high/30 bg-status-high-bg px-3 py-2 text-sm text-status-high">
            <XCircle className="h-4 w-4" /> {error}
          </p>
        )}
      </section>

      {result && (
        <section className="grid gap-6 xl:grid-cols-[1fr_1.25fr]">
          <div className="space-y-4">
            <div className={cn('rounded-xl border p-5', (STATUS_UI[result.overall_status] ?? STATUS_UI.NOT_VERIFIED).cls)}>
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-6 w-6" aria-hidden="true" />
                <h2 className="text-lg font-semibold tracking-wide">{result.officer_summary.headline}</h2>
              </div>
              <p className="mt-2 text-sm opacity-90">{result.explanation}</p>
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm text-foreground">
                {Object.entries(result.officer_summary.facts).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs text-muted-foreground">{k}</dt>
                    <dd className="font-medium">{v}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-xs text-muted-foreground">Risk indicator</dt>
                  <dd className="font-medium">{result.risk_score}/100 · {humanize(result.risk_level)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Evidence completeness</dt>
                  <dd className="font-medium">{Math.round(result.confidence * 100)}%</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="mb-3 text-sm font-semibold">Checklist</h3>
              <ul className="space-y-2">
                {result.officer_summary.lines.map((l, i) => {
                  const Icon = LINE_ICON[l.icon]
                  return (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', LINE_CLS[l.icon])} aria-hidden="true" />
                      <span>{l.text}</span>
                    </li>
                  )
                })}
              </ul>
              <p className="mt-4 text-xs text-muted-foreground">{result.officer_summary.responsibility_notice}</p>
            </div>

            {result.id && (
              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="mb-3 text-sm font-semibold">Officer decision</h3>
                <textarea
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  placeholder="Reason (required unless clearing)"
                  className="mb-3 h-20 w-full rounded-md border border-border bg-input px-3 py-2 text-sm"
                />
                <div className="flex flex-wrap gap-2">
                  {ACTIONS.map((a) => (
                    <button key={a.value} type="button" onClick={() => submitAction(a)}
                      className="rounded-md border border-border bg-secondary px-3 py-2 text-sm hover:border-accent">
                      {a.label}
                    </button>
                  ))}
                </div>
                {actionDone && <p className="mt-3 text-sm text-muted-foreground">{actionDone}</p>}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-border bg-card p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {([
                ['evidence', 'View evidence', ScanSearch],
                ['data', 'Extracted data', FileImage],
                ['document', 'Document', FileImage],
                ['history', 'Verification history', History],
              ] as const).map(([key, label, Icon]) => (
                <button key={key} type="button" onClick={() => setTab(key)}
                  className={cn('inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm',
                    tab === key ? 'bg-accent text-accent-foreground' : 'bg-secondary text-muted-foreground')}>
                  <Icon className="h-4 w-4" aria-hidden="true" /> {label}
                </button>
              ))}
              {result.documents.length > 1 && tab !== 'history' && (
                <select value={docIndex} onChange={(e) => setDocIndex(Number(e.target.value))}
                  className="ml-auto rounded-md border border-border bg-input px-2 py-1.5 text-sm">
                  {result.documents.map((d) => (
                    <option key={d.document_index} value={d.document_index}>
                      Document {d.document_index + 1}: {humanize(d.document_type.document_type)}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {tab === 'evidence' && (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setActiveCheck(null)}
                    className={cn('rounded-full border px-2.5 py-1 text-xs', !activeCheck ? 'border-accent text-accent' : 'border-border text-muted-foreground')}>
                    All regions
                  </button>
                  {result.check_details
                    .filter((c) => c.document_index === docIndex && c.evidence_ids.length && c.status !== 'NOT_APPLICABLE')
                    .map((c, i) => (
                      <button key={`${c.name}-${i}`} type="button" onClick={() => setActiveCheck(c.name)}
                        className={cn('inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs',
                          activeCheck === c.name ? 'border-accent text-accent' : 'border-border text-muted-foreground')}>
                        {c.status === 'PASS' ? '✓' : c.status === 'REVIEW_REQUIRED' || c.status === 'FAIL' ? '⚠' : 'ℹ'} {humanize(c.name)}
                      </button>
                    ))}
                </div>
                <EvidenceViewer src={previews[docIndex] ?? null} size={doc?.image_size ?? null} evidence={docEvidence} activeIds={activeIds} />
                <ul className="space-y-2">
                  {result.check_details
                    .filter((c) => (c.document_index === docIndex || c.document_index === null) && c.status !== 'NOT_APPLICABLE')
                    .filter((c) => !activeCheck || c.name === activeCheck)
                    .map((c, i) => (
                      <li key={i} className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
                        <div>
                          <p className="font-medium">{humanize(c.name)}{!c.blocking && <span className="ml-2 text-xs text-muted-foreground">(advisory)</span>}</p>
                          <p className="text-muted-foreground">{c.summary}</p>
                        </div>
                        <StatusPill status={c.status} />
                      </li>
                    ))}
                </ul>
              </div>
            )}

            {tab === 'data' && doc && (
              <div className="space-y-5 text-sm">
                <p className="text-muted-foreground">
                  Identified as <span className="text-foreground">{humanize(doc.document_type.document_type)}</span>
                  {doc.document_type.country ? ` (${humanize(doc.document_type.country)})` : ''}
                  {doc.template_version ? ` · template ${doc.template_version}` : ''}
                </p>
                <table className="w-full text-left">
                  <thead className="text-xs text-muted-foreground">
                    <tr><th className="py-1">Field</th><th>Value</th><th>Source</th><th>Read confidence</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(doc.fields).map(([k, f]) => (
                      <tr key={k} className="border-t border-border">
                        <td className="py-1.5">{humanize(k)}</td>
                        <td className="font-medium">{f.value}</td>
                        <td className="text-muted-foreground">{f.source}</td>
                        <td className="text-muted-foreground">{Math.round(f.confidence * 100)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {doc.mrz && !('format_error' in doc.mrz) && (
                  <div>
                    <h4 className="mb-1 font-semibold">Machine-readable zone</h4>
                    <p className="text-muted-foreground">
                      {String(doc.mrz.format)} · number {String(doc.mrz.document_number)} · check digits{' '}
                      {doc.mrz.all_checks_valid ? 'all correct' : `failed: ${(doc.mrz.failed_checks as string[]).join(', ')}`}
                    </p>
                  </div>
                )}
                {doc.stamps.length > 0 && (
                  <div>
                    <h4 className="mb-1 font-semibold">Stamps</h4>
                    <ul className="space-y-1">
                      {doc.stamps.map((s) => (
                        <li key={s.region_id} className="text-muted-foreground">
                          {humanize(s.stamp_type)} — {[s.country, s.checkpoint, s.direction, s.date].filter(Boolean).join(' · ') || 'text not readable'}
                          {s.missing_fields.length > 0 && ` (not read: ${s.missing_fields.join(', ')})`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.cross_document.length > 0 && (
                  <div>
                    <h4 className="mb-1 font-semibold">Consistency comparisons</h4>
                    <ul className="space-y-1">
                      {result.cross_document.map((r) => (
                        <li key={String(r.id)} className="flex gap-2">
                          <span aria-hidden="true">{r.result === 'CONSISTENT' ? '✓' : '⚠'}</span>
                          <span className={r.result === 'CONSISTENT' ? 'text-muted-foreground' : ''}>{String(r.explanation)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {tab === 'document' && (
              previews[docIndex]
                ? <img src={previews[docIndex]} alt="Submitted document" className="w-full rounded-lg border border-border" />
                : <p className="text-sm text-muted-foreground">Images are not stored on the server (minimum data retention).</p>
            )}

            {tab === 'history' && (
              <ul className="divide-y divide-border text-sm">
                {history.map((h) => (
                  <li key={h.id} className="flex items-center justify-between gap-3 py-2">
                    <button type="button" onClick={() => openStored(h.id)} className="text-left hover:text-accent">
                      <p className="font-medium">#{h.sequence} · {h.document_types.map(humanize).join(', ')}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(h.created_at).toLocaleString()} · {humanize(h.source)} · officer: {humanize(h.officer_action)}
                        {h.captured_offline ? ' · captured offline' : ''}
                      </p>
                    </button>
                    <StatusPill status={h.overall_status} />
                  </li>
                ))}
                {!history.length && <li className="py-4 text-muted-foreground">No verifications yet.</li>}
              </ul>
            )}
          </div>
        </section>
      )}
      <p className="text-xs text-muted-foreground">
        Images are processed in memory and are not stored. Registry lookups use fictional mock data only; no real government database is accessed.
      </p>
    </div>
  )
}

export default DocumentVerification
