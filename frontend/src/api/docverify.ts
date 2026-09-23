import { apiClient } from './client'

// Types mirror app/services/docverify/types.py (subset used by the UI).
export type CheckStatus =
  | 'PASS'
  | 'REVIEW_REQUIRED'
  | 'NOT_VERIFIED'
  | 'REGISTRY_NOT_AVAILABLE'
  | 'OFFICIAL_VERIFICATION_REQUIRED'
  | 'REFERENCE_NOT_AVAILABLE'
  | 'NOT_APPLICABLE'
  | 'FAIL'

export interface Evidence {
  id: string
  check: string
  description: string
  region_id: string | null
  bbox: number[] | null
  document_index: number | null
  values: Record<string, unknown>
}

export interface CheckResult {
  name: string
  status: CheckStatus
  summary: string
  blocking: boolean
  strong_evidence: boolean
  evidence_ids: string[]
  details: Record<string, unknown>
  document_index: number | null
}

export interface FieldValue {
  value: string
  confidence: number
  source: string
  bbox: number[] | null
}

export interface Region {
  id: string
  label: string
  bbox: number[]
  confidence: number
  source: string
}

export interface StampResult {
  region_id: string
  stamp_type: string
  identification: string
  country: string | null
  authority: string | null
  checkpoint: string | null
  checkpoint_type: string | null
  direction: string | null
  date: string | null
  missing_fields: string[]
  reference_match: string
  bbox: number[] | null
}

export interface DocumentAnalysis {
  document_index: number
  image_size: number[] | null
  document_type: { document_type: string; country: string | null; confidence: number; basis: string[] }
  template_version: string | null
  regions: Region[]
  fields: Record<string, FieldValue>
  mrz: Record<string, unknown> | null
  codes: { region_id: string; symbology: string; decoded: boolean; payload_kind: string }[]
  stamps: StampResult[]
}

export interface VerificationOutcome {
  id: string | null
  overall_status: CheckStatus
  country: string | null
  document_type: string
  checkpoint_type: string | null
  border_route: string | null
  confidence: number
  explanation: string
  risk_score: number
  risk_level: string
  risk_breakdown: { check: string; status: string; points: number; reason: string }[]
  checks: Record<string, CheckStatus>
  check_details: CheckResult[]
  flags: string[]
  advisories: string[]
  evidence: Evidence[]
  documents: DocumentAnalysis[]
  cross_document: Record<string, unknown>[]
  officer_summary: {
    headline: string
    facts: Record<string, string>
    lines: { icon: 'ok' | 'warn' | 'info' | 'fail'; text: string }[]
    responsibility_notice: string
  }
  connectivity: string
  pipeline: Record<string, unknown>
  data_notice: string
  generated_at: string
  suggested_reasons?: { clear?: string; send?: string }
  case?: {
    case_id?: string
    case_number?: string
    screening_verification_id?: string
    status?: string
    decisions?: { decision: string; reason: string | null; at: string; username: string | null; role: string | null }[]
    notes?: { note: string; at: string; username: string | null; role: string | null }[]
  } | null
  identity?: {
    face_cluster?: { status: string; cluster_size: number; members: { record_id: string; reference_name: string; document_number: string | null }[]; reason: string } | null
    duplicate_document?: { status: string; match_count: number; reason: string } | null
    notes?: string[]
  } | null
}

export interface VerificationListItem {
  id: string
  sequence: number
  created_at: string
  source: string
  document_types: string[]
  country: string | null
  border_route: string | null
  overall_status: CheckStatus
  risk_score: number
  risk_level: string
  officer_action: string
  sync_status: string
  captured_offline: boolean
}

export interface VerificationEnvelope {
  record: VerificationListItem
  integrity: { hash_valid: boolean; signature_valid: boolean }
  officer_action: { action: string; reason: string | null; by: string | null; at: string | null }
  result: VerificationOutcome
}

export type OfficerAction =
  | 'CLEARED'
  | 'REFERRED_FOR_SECONDARY_INSPECTION'
  | 'RECAPTURE_REQUESTED'
  | 'OFFICIAL_VERIFICATION_REQUESTED'

export interface VerifyParams {
  files: File[]
  liveFace?: File | null
  borderRoute?: string
  direction?: string
  declaredNationality?: string
}

export async function verifyDocuments(p: VerifyParams): Promise<VerificationOutcome> {
  const form = new FormData()
  p.files.forEach((f) => form.append('files', f))
  if (p.liveFace) form.append('live_face', p.liveFace)
  if (p.borderRoute) form.append('border_route', p.borderRoute)
  if (p.direction) form.append('direction', p.direction)
  if (p.declaredNationality) form.append('declared_nationality', p.declaredNationality)
  const { data } = await apiClient.post<VerificationOutcome>('/api/v1/verify/document', form, { timeout: 180000 })
  return data
}

export async function listDocumentVerifications(limit = 30): Promise<VerificationListItem[]> {
  const { data } = await apiClient.get<VerificationListItem[]>('/api/v1/verification', { params: { limit } })
  return data
}

export async function getDocumentVerification(id: string): Promise<VerificationEnvelope> {
  const { data } = await apiClient.get<VerificationEnvelope>(`/api/v1/verification/${id}`)
  return data
}

export async function recordOfficerAction(id: string, action: OfficerAction, reason?: string) {
  const { data } = await apiClient.post<VerificationListItem>(`/api/v1/verification/${id}/officer-action`, {
    action,
    reason: reason || null,
  })
  return data
}

/** The document verification behind a screening case (404 for cases that
 * came from the older screening flow). */
export async function getVerificationByCase(caseId: string): Promise<VerificationEnvelope | null> {
  try {
    const { data } = await apiClient.get<VerificationEnvelope>(`/api/v1/verification/by-case/${caseId}`)
    return data
  } catch (e: unknown) {
    if ((e as { response?: { status?: number } }).response?.status === 404) return null
    throw e
  }
}
