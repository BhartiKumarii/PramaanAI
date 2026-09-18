import { useState } from 'react'
import { FlaskConical, Play, ImageOff } from 'lucide-react'
import { listTestScenarios, previewTestScenario, runTestScenario } from '../api/resources'
import { useAsync } from '../hooks/useAsync'
import { Card } from '../components/StatTile'
import type { TestScenarioPreview, TestScenarioRunResult } from '../api/types'

const LEVEL_CLASS: Record<string, string> = {
  LOW_RISK: 'text-status-clear',
  MEDIUM_RISK: 'text-status-review',
  HIGH_RISK: 'text-status-high',
  LOW: 'text-status-clear',
  MEDIUM: 'text-status-review',
  HIGH: 'text-status-high',
}

export function TestingMode() {
  const scenarios = useAsync(listTestScenarios, [])
  const [selected, setSelected] = useState<string | null>(null)
  const [preview, setPreview] = useState<TestScenarioPreview | null>(null)
  const [result, setResult] = useState<TestScenarioRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function selectScenario(id: string) {
    setSelected(id)
    setResult(null)
    setError(null)
    setLoading(true)
    try {
      setPreview(await previewTestScenario(id))
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not generate scenario.')
      setPreview(null)
    } finally {
      setLoading(false)
    }
  }

  async function handleRun() {
    if (!selected) return
    setRunning(true)
    setError(null)
    try {
      setResult(await runTestScenario(selected))
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(detail ?? 'Could not run scenario through the pipeline.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-foreground">
          <FlaskConical className="h-5 w-5 text-accent" />
          Testing Mode
        </h1>
        <p className="text-sm text-muted-foreground">
          Synthetic scenarios only — no real documents. Each scenario runs through the exact same
          screening pipeline a real device hits (POST /documents/screen). "Designed to exercise" is a
          hand-written hypothesis about what a scenario should trigger; "Actual result" is what the real
          risk engine just computed — they're shown side by side so you can see whether they agree, not
          because one confirms the other automatically.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Scenarios" className="lg:col-span-1">
          {scenarios.loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {scenarios.error && <p className="text-sm text-status-high">{scenarios.error}</p>}
          {scenarios.data && (
            <div className="max-h-[70vh] space-y-1 overflow-y-auto">
              {scenarios.data.map((s) => (
                <button
                  key={s.id}
                  onClick={() => selectScenario(s.id)}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                    selected === s.id
                      ? 'bg-accent/10 text-accent'
                      : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-4 lg:col-span-2">
          {error && <p className="text-sm text-status-high">{error}</p>}
          {loading && <p className="text-sm text-muted-foreground">Generating synthetic scenario…</p>}

          {preview && !loading && (
            <Card title={preview.scenario.replace(/_/g, ' ')}>
              <p className="text-sm text-muted-foreground">{preview.description}</p>

              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">Document image</p>
                  {preview.document_image ? (
                    <img
                      src={`data:image/png;base64,${preview.document_image}`}
                      alt="Synthetic document"
                      className="w-full rounded-md border border-border"
                    />
                  ) : (
                    <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-border text-muted-foreground">
                      <ImageOff className="h-5 w-5" />
                    </div>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">Selfie image</p>
                  {preview.selfie_image ? (
                    <img
                      src={`data:image/png;base64,${preview.selfie_image}`}
                      alt="Synthetic selfie"
                      className="w-full rounded-md border border-border"
                    />
                  ) : (
                    <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-border text-muted-foreground">
                      <ImageOff className="h-5 w-5" />
                    </div>
                  )}
                </div>
              </div>

              {Object.keys(preview.ocr_fields).length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(preview.ocr_fields).map(([k, v]) => (
                    <div key={k} className="flex justify-between border-b border-border py-1">
                      <span className="text-muted-foreground">{k}</span>
                      <span className="text-foreground">{v}</span>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={handleRun}
                disabled={running}
                className="mt-4 flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
              >
                <Play className="h-4 w-4" />
                {running ? 'Running through real pipeline…' : 'Run through real pipeline'}
              </button>
            </Card>
          )}

          {result && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Card title="Designed to exercise (hypothesis)">
                <p className={`text-lg font-semibold ${LEVEL_CLASS[result.designed_to_exercise.expected_risk_level] ?? 'text-foreground'}`}>
                  {result.designed_to_exercise.expected_risk_level}
                </p>
                <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {result.designed_to_exercise.expected_issues.length === 0 && <li>No issues expected.</li>}
                  {result.designed_to_exercise.expected_issues.map((issue) => (
                    <li key={issue}>• {issue}</li>
                  ))}
                </ul>
              </Card>

              <Card title="Actual result (real risk engine)">
                <p className={`text-lg font-semibold ${LEVEL_CLASS[result.actual_result.risk.level] ?? 'text-foreground'}`}>
                  {result.actual_result.risk.level} · {result.actual_result.risk.decision}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Score: {result.actual_result.risk.score}/100</p>
                <p className="mt-2 text-xs text-foreground">{result.actual_result.risk.top_reason}</p>
                <ul className="mt-3 space-y-1.5 border-t border-border pt-3 text-xs">
                  {result.actual_result.risk.breakdown.map((b) => (
                    <li key={b.signal} className="flex justify-between text-muted-foreground">
                      <span>{b.signal.replace(/_/g, ' ')}</span>
                      <span className="text-foreground">{b.reason}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          )}

          {!preview && !loading && (
            <Card>
              <p className="py-8 text-center text-sm text-muted-foreground">
                Pick a scenario from the list to generate its synthetic document/selfie, then run it
                through the real pipeline.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
