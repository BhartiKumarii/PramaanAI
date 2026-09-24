import { useEffect, useMemo, useState } from 'react'
import { baseURL } from '../api/client'
import { getVerificationByCase, type CheckResult, type VerificationEnvelope, type VerificationOutcome } from '../api/docverify'

/* Document verification behind a screening case, for the reviewing admin:
 * what the field officer's phone captured (document image + live photo,
 * attached as the case's evidence), every finding boxed on the document,
 * the extracted fields with their source, face match, identity links and the
 * officer's message. Status is always icon + words + colour. Renders nothing
 * for cases from the older screening flow. */

const STATUS: Record<string, { label: string; icon: string; cls: string }> = {
  PASS: { label: 'Passed', icon: '✓', cls: 'text-status-clear' },
  REVIEW_REQUIRED: { label: 'Review required', icon: '⚠', cls: 'text-status-review' },
  FAIL: { label: 'Check failed', icon: '✕', cls: 'text-status-high' },
  NOT_VERIFIED: { label: 'Not verified', icon: 'ⓘ', cls: 'text-muted-foreground' },
  REGISTRY_NOT_AVAILABLE: { label: 'Registry not available', icon: 'ⓘ', cls: 'text-sky-400' },
  OFFICIAL_VERIFICATION_REQUIRED: { label: 'Official verification required', icon: 'ⓘ', cls: 'text-sky-400' },
  REFERENCE_NOT_AVAILABLE: { label: 'No reference available', icon: 'ⓘ', cls: 'text-muted-foreground' },
  NOT_APPLICABLE: { label: 'Not applicable', icon: '–', cls: 'text-muted-foreground' },
}

const SOURCE: Record<string, { label: string; cls: string }> = {
  mrz: { label: 'MRZ', cls: 'border-sky-500/50 text-sky-400' },
  qr: { label: 'QR', cls: 'border-violet-500/50 text-violet-400' },
  barcode: { label: 'Barcode', cls: 'border-violet-500/50 text-violet-400' },
  device: { label: 'Read on phone', cls: 'border-amber-500/50 text-amber-400' },
  ocr: { label: 'Read by server', cls: 'border-emerald-500/50 text-emerald-400' },
  ocr_devanagari: { label: 'Devanagari', cls: 'border-emerald-500/50 text-emerald-400' },
}

const FIELD_ORDER = ['name', 'surname', 'given_names', 'document_number', 'aadhaar_number', 'visa_number', 'permit_number',
  'nationality', 'sex', 'date_of_birth', 'place_of_birth', 'date_of_issue', 'valid_from', 'date_of_expiry',
  'issuing_authority', 'vehicle_classes', 'visa_type', 'entries', 'duration']

const FIELD_LABEL: Record<string, string> = {
  name_native: 'Name (Devanagari)',
  date_of_birth_bs: 'Date of birth (Bikram Sambat)',
  national_id_number: 'National ID number',
  citizenship_number: 'Citizenship certificate number',
  sex_native: 'Sex (Devanagari)',
}

const human = (s: string) => s.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())

function useAuthImage(path: string | null) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    if (!path) return
    let url: string | null = null
    const token = localStorage.getItem('bsa_access_token') ?? ''
    fetch(`${baseURL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((b) => { url = URL.createObjectURL(b); setSrc(url) })
      .catch(() => setSrc(null))
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [path])
  return src
}

function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  )
}

export function DocVerifyCasePanel({ caseId, onLoaded }: { caseId: string; onLoaded?: (result: VerificationOutcome | null) => void }) {
  const [env, setEnv] = useState<VerificationEnvelope | null | undefined>(undefined)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [showPassed, setShowPassed] = useState(false)
  const [copied, setCopied] = useState('')

  useEffect(() => {
    getVerificationByCase(caseId)
      .then((e) => { setEnv(e); onLoaded?.(e?.result ?? null) })
      .catch(() => { setError('Could not load the document verification for this case.'); onLoaded?.(null) })
  }, [caseId]) // eslint-disable-line react-hooks/exhaustive-deps

  const r = env?.result
  const evidenceById = useMemo(() => Object.fromEntries((r?.evidence ?? []).map((e) => [e.id, e])), [r])
  const sid = r?.case?.screening_verification_id ?? null
  const docImg = useAuthImage(sid ? `/images/${sid}/document` : null)
  const liveImg = useAuthImage(sid ? `/images/${sid}/selfie` : null)

  if (env === undefined && !error) return <p className="text-sm text-muted-foreground">Loading document verification…</p>
  if (error) return <p className="text-sm text-status-high">{error}</p>
  if (!r) return null

  const doc = r.documents[0]
  const size = doc?.image_size ?? null
  const relevant = r.check_details.filter((c) => c.status !== 'NOT_APPLICABLE')
  const issues = relevant.filter((c) => c.status === 'FAIL' || c.status === 'REVIEW_REQUIRED')
  const notVerified = relevant.filter((c) => !['FAIL', 'REVIEW_REQUIRED', 'PASS'].includes(c.status))
  const passed = relevant.filter((c) => c.status === 'PASS')
  const boxesFor = (c: CheckResult) => c.evidence_ids.map((id) => evidenceById[id]).filter((e) => e?.bbox && (e.document_index ?? 0) === 0)
  const shownIssues = selected ? issues.filter((c) => c.name === selected) : issues
  const problemBoxes = shownIssues.flatMap(boxesFor)
  const photoBox = relevant.filter((c) => c.name === 'photo' || c.name === 'face_verification').flatMap(boxesFor)[0]?.bbox ?? null
  const face = relevant.find((c) => c.name === 'face_verification')
  const st = STATUS[r.overall_status] ?? STATUS.NOT_VERIFIED
  const fields = doc?.fields ?? {}
  const orderedFields = [...FIELD_ORDER.filter((k) => k in fields), ...Object.keys(fields).filter((k) => !FIELD_ORDER.includes(k)).sort()]
  const officerNote = r.case?.notes?.find((n) => n.role !== 'REVIEWER')
  const copy = (label: string, text?: string) => {
    if (!text) return
    navigator.clipboard?.writeText(text).then(() => { setCopied(label); setTimeout(() => setCopied(''), 1500) })
  }

  return (
    <div className="space-y-4">
      <Section title="Document verification (field officer's phone)"
        right={<span className="text-xs text-muted-foreground">risk indicator {r.risk_score}/100 · {human(r.risk_level)}</span>}>
        <p className={`text-base font-bold ${st.cls}`}>{st.icon} {r.officer_summary?.headline ?? st.label}</p>
        {r.explanation && <p className="mt-1 text-sm text-muted-foreground">{r.explanation}</p>}
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
          {Object.entries(r.officer_summary?.facts ?? {}).map(([k, v]) => (
            <div key={k}><dt className="text-muted-foreground">{k}</dt><dd className="font-medium text-foreground">{v}</dd></div>
          ))}
        </dl>
        {officerNote && (
          <div className="mt-3 rounded-md border border-sky-500/40 bg-sky-500/10 p-3 text-sm">
            <p className="text-xs font-semibold text-sky-400">Message from {officerNote.username ?? 'the field officer'}</p>
            <p className="mt-1 text-foreground">{officerNote.note}</p>
          </div>
        )}
      </Section>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Section title={problemBoxes.length ? `Document — problem areas marked (${problemBoxes.length})` : 'Document'}
            right={selected ? <button className="text-xs text-accent" onClick={() => setSelected(null)}>Show all</button> : null}>
            {docImg && size ? (
              <div className="relative w-full overflow-hidden rounded-md border border-border">
                <img src={docImg} alt="Document captured by the field officer" className="block w-full" />
                <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${size[0]} ${size[1]}`} preserveAspectRatio="none">
                  {problemBoxes.map((e, i) => {
                    const [x0, y0, x1, y1] = e!.bbox!
                    return <rect key={i} x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="rgba(241,77,76,0.14)"
                      stroke="rgb(241,77,76)" strokeWidth={Math.max(2, size[0] / 400)} />
                  })}
                </svg>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No document image is attached to this case (captured before images were kept with the record).
              </p>
            )}
          </Section>
        </div>
        <div className="space-y-4 lg:col-span-2">
          <Section title="Face match">
            <div className="flex gap-3">
              <figure className="flex-1">
                <div className="aspect-square overflow-hidden rounded-md border border-border bg-secondary">
                  {docImg && photoBox && size ? (
                    <svg viewBox={`${photoBox[0]} ${photoBox[1]} ${photoBox[2] - photoBox[0]} ${photoBox[3] - photoBox[1]}`}
                      className="h-full w-full" preserveAspectRatio="xMidYMid slice">
                      <image href={docImg} x={0} y={0} width={size[0]} height={size[1]} />
                    </svg>
                  ) : <div className="flex h-full items-center justify-center text-xs text-muted-foreground">—</div>}
                </div>
                <figcaption className="mt-1 text-center text-xs text-muted-foreground">Document photo</figcaption>
              </figure>
              <figure className="flex-1">
                <div className="aspect-square overflow-hidden rounded-md border border-border bg-secondary">
                  {liveImg ? <img src={liveImg} alt="Live photo" className="h-full w-full object-cover" />
                    : <div className="flex h-full items-center justify-center text-xs text-muted-foreground">No live photo</div>}
                </div>
                <figcaption className="mt-1 text-center text-xs text-muted-foreground">Live photo</figcaption>
              </figure>
            </div>
            {face ? (
              <p className={`mt-2 text-sm ${(STATUS[face.status] ?? STATUS.NOT_VERIFIED).cls}`}>
                {(STATUS[face.status] ?? STATUS.NOT_VERIFIED).icon} {face.summary}
                {typeof face.details?.similarity_score === 'number' && (
                  <span className="text-muted-foreground"> · similarity {(face.details.similarity_score as number).toFixed(2)} (match ≥ 0.50)</span>
                )}
              </p>
            ) : <p className="mt-2 text-sm text-muted-foreground">No live photo was compared.</p>}
          </Section>
          <Section title="Identity links">
            {r.identity ? (
              <ul className="space-y-1.5 text-sm">
                <li className={r.identity.face_cluster?.status === 'CLUSTER_FOUND' ? 'text-status-review' : 'text-status-clear'}>
                  {r.identity.face_cluster?.status === 'CLUSTER_FOUND'
                    ? `⚠ Same face under another identity — ${r.identity.face_cluster.reason}`
                    : '✓ No earlier screening shows this face under another name'}
                </li>
                {r.identity.face_cluster?.members?.filter((m) => m.reference_name).map((m) => (
                  <li key={m.record_id} className="ml-4 text-xs text-muted-foreground">• {m.reference_name} {m.document_number ? `· ${m.document_number}` : ''}</li>
                ))}
                {r.identity.duplicate_document && (
                  <li className={r.identity.duplicate_document.status === 'DIFFERENT_IDENTITY_REUSE' ? 'text-status-review' : 'text-muted-foreground'}>
                    {r.identity.duplicate_document.status === 'NO_MATCH' ? '✓ Document number not seen on other cases'
                      : r.identity.duplicate_document.status === 'SAME_IDENTITY_REUSE'
                        ? `ⓘ Seen before with the same identity (${r.identity.duplicate_document.match_count}×)`
                        : `⚠ ${r.identity.duplicate_document.reason}`}
                  </li>
                )}
                {r.identity.notes?.map((n) => <li key={n} className="text-xs text-muted-foreground">{n}</li>)}
              </ul>
            ) : <p className="text-sm text-muted-foreground">Not built for this verification.</p>}
          </Section>
        </div>
      </div>

      {issues.length > 0 && (
        <Section title={`Needs attention (${issues.length})`} right={<span className="text-xs text-muted-foreground">click to mark on the document</span>}>
          <ul className="divide-y divide-border">
            {issues.map((c) => {
              const s = STATUS[c.status] ?? STATUS.NOT_VERIFIED
              return (
                <li key={c.name + c.summary}>
                  <button onClick={() => setSelected(selected === c.name ? null : c.name)}
                    className={`flex w-full items-start gap-3 py-2 text-left ${selected === c.name ? 'bg-secondary/60' : ''}`}>
                    <span className={`mt-0.5 ${s.cls}`}>{s.icon}</span>
                    <span className="flex-1">
                      <span className="text-sm font-medium text-foreground">{human(c.name)}{!c.blocking && ' (advisory)'}</span>
                      <span className="block text-xs text-muted-foreground">{c.summary}</span>
                    </span>
                    <span className={`text-xs ${s.cls}`}>{s.label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </Section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={`Extracted details — ${human(doc?.document_type.document_type ?? 'document')}`}>
          {orderedFields.length === 0 ? <p className="text-sm text-muted-foreground">No printed details could be read.</p> : (
            <dl className="divide-y divide-border/50">
              {orderedFields.map((k) => {
                const f = fields[k]
                const src = SOURCE[f.source] ?? SOURCE.ocr
                return (
                  <div key={k} className="flex items-center justify-between gap-3 py-1.5">
                    <dt className="text-xs text-muted-foreground">{FIELD_LABEL[k] ?? human(k)}</dt>
                    <dd className="flex items-center gap-2 text-sm font-medium text-foreground">
                      {f.value}
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] ${src.cls}`}>{src.label}</span>
                    </dd>
                  </div>
                )
              })}
            </dl>
          )}
        </Section>
        <div className="space-y-4">
          {notVerified.length > 0 && (
            <Section title={`Not verified here (${notVerified.length})`}>
              <ul className="space-y-1.5">
                {notVerified.map((c) => (
                  <li key={c.name + c.summary} className="text-sm"><span className="text-sky-400">ⓘ</span> <span className="font-medium">{human(c.name)}</span>
                    <span className="block text-xs text-muted-foreground">{c.summary}</span></li>
                ))}
              </ul>
            </Section>
          )}
          <Section title={`Passed checks (${passed.length})`}
            right={<button className="text-xs text-accent" onClick={() => setShowPassed(!showPassed)}>{showPassed ? 'Hide' : 'Show'}</button>}>
            {showPassed ? (
              <ul className="space-y-1">
                {passed.map((c) => <li key={c.name + c.summary} className="text-xs"><span className="text-status-clear">✓</span> {human(c.name)} — <span className="text-muted-foreground">{c.summary}</span></li>)}
              </ul>
            ) : <p className="text-xs text-muted-foreground">{passed.length} checks passed.</p>}
          </Section>
          {r.suggested_reasons && (
            <Section title="Suggested wording for your response">
              {(['send', 'clear'] as const).map((k) => r.suggested_reasons?.[k] && (
                <div key={k} className="mb-2 rounded-md border border-border p-2 text-xs">
                  <p className="text-foreground">{r.suggested_reasons[k]}</p>
                  <button className="mt-1 text-accent" onClick={() => copy(k, r.suggested_reasons?.[k])}>
                    {copied === k ? 'Copied' : 'Copy'}
                  </button>
                </div>
              ))}
            </Section>
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{r.data_notice} The system assists; the reviewing officer decides.</p>
    </div>
  )
}
