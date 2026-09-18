// Mirrors the FastAPI Pydantic schemas — see app/schemas/*.py. Kept as
// plain interfaces (not generated) since the backend is still moving;
// field names are copied verbatim so a mismatch is a compile error here,
// not a silent runtime one.

export type Role = 'OFFICER'

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  role: Role
}

export interface CurrentUser {
  id: string
  username: string
  role: Role
}

export interface Checkpoint {
  id: string
  code: string
  name: string
  location: string | null
  is_active: boolean
}

// --- evidence signals (see app/schemas/verification.py) ---

export interface OCRResult {
  document_type: string
  fields: Record<string, string>
  ocr_confidence: number
}

export interface ValidationFinding {
  check: string
  status: 'PASS' | 'FAIL'
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  reason: string
}

export interface ValidationResult {
  status: 'PASS' | 'FAIL'
  findings: ValidationFinding[]
}

export interface TamperingFinding {
  type: string
  confidence: number
  reason: string
  location: Record<string, number> | null
}

export interface TamperingResult {
  tampering_risk: number
  findings: TamperingFinding[]
}

export interface DeepfakeResult {
  status: 'ANALYZED' | 'NOT_IMPLEMENTED'
  score: number | null
  reason: string
}

export interface RegistryHit {
  full_name: string
  registry_reason: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  match_type: 'EXACT' | 'FUZZY'
  confidence: number
  matched_field: string
  explanation: string
}

export interface RegistryLookupResult {
  status: 'HIT' | 'NO_HIT'
  hits: RegistryHit[]
}

export interface FaceMatchResult {
  match: boolean
  similarity: number
  confidence: number
  reason: string
}

export interface IdentityClusterMember {
  record_id: string
  reference_name: string
  document_number: string | null
}

export interface IdentityGraphResult {
  status: 'CLUSTER_FOUND' | 'NO_CLUSTER'
  cluster_size: number
  members: IdentityClusterMember[]
  reason: string
}

export interface LivenessResult {
  status: 'LIVE' | 'SUSPECTED_SPOOF' | 'NOT_IMPLEMENTED'
  score: number | null
  reason: string
}

export interface RiskSignalBreakdown {
  signal: string
  weight: number
  raw_risk: number
  contribution: number
  reason: string
}

export interface RiskResult {
  score: number
  level: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK'
  decision: 'CLEAR' | 'MANUAL_REVIEW'
  top_reason: string
  breakdown: RiskSignalBreakdown[]
}

export interface VerificationRecordResponse {
  id: string
  document_type: string
  nationality: string
  traveler_name: string | null
  risk: RiskResult
  signature_valid: boolean
  created_at: string
  ocr: OCRResult | null
  validation: ValidationResult | null
  tampering: TamperingResult | null
  deepfake: DeepfakeResult | null
  registry: RegistryLookupResult | null
  face: FaceMatchResult | null
  identity_graph: IdentityGraphResult | null
  liveness: LivenessResult | null
}

export interface ScreeningResponse extends VerificationRecordResponse {
  verification_id: string
  case_id: string
  case_number: string
  case_status: string
}

// --- cases (see app/schemas/case.py) ---

export type CaseStatus =
  | 'PENDING_SYNC'
  | 'PENDING'
  | 'SENT'
  | 'REVIEW_REQUIRED'
  | 'CLEAR'
  | 'SECONDARY_REVIEW'
  | 'HOLD_REFER'

export type CasePriority = 'LOW' | 'MEDIUM' | 'HIGH'
export type DecisionValue = 'CLEAR' | 'SECONDARY_REVIEW' | 'HOLD_REFER'

export interface CaseListItem {
  id: string
  case_number: string
  status: CaseStatus
  priority: CasePriority
  checkpoint_code: string
  field_officer_username: string
  assigned_officer_username: string | null
  document_type: string
  nationality: string
  traveler_name: string | null
  created_at: string
  sent_at: string | null
}

export interface CaseDecisionSummary {
  decision: string
  officer_username: string | null
  reason: string | null
  created_at: string
}

export interface CaseNote {
  id: string
  author_username: string | null
  note: string
  created_at: string
}

export interface CaseDetail extends CaseListItem {
  verification: VerificationRecordResponse | null
  notes: CaseNote[]
  decisions: CaseDecisionSummary[]
  decided_at: string | null
}

export interface AuditEvent {
  id: string
  event_type: string
  actor_user_id: string
  actor_username: string | null
  reason: string | null
  created_at: string
}

export interface AuditLogEntry {
  id: string
  event_type: string
  actor_user_id: string
  actor_username: string | null
  actor_role: string | null
  case_id: string | null
  case_number: string | null
  reason: string | null
  created_at: string
}

export interface TimelineEvent {
  event_type: string
  action: string
  actor_username: string | null
  detail: string | null
  created_at: string
}

export interface IdentityHistoryRecord {
  record_id: string
  case_id: string | null
  case_number: string | null
  checkpoint_code: string | null
  declared_name: string
  masked_document_number: string | null
  occurred_at: string | null
  similarity: number | null
  review_status: string | null
}

// --- network (see app/schemas/network.py) ---

export interface GraphNode {
  id: string
  type: string
  label: string
  detail: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relationship_type: string
  explanation: string
  evidence_case_id: string | null
  created_at: string
}

export interface NetworkGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface RelationshipListItem {
  id: string
  source_type: string
  source_id: string
  target_type: string
  target_id: string
  relationship_type: string
  explanation: string
  evidence_case_id: string | null
  created_at: string
}

export interface PersonSearchResult {
  id: string
  full_name: string
  masked_document_number: string | null
  nationality: string | null
  created_at: string
}

// --- dashboards (see app/schemas/dashboard.py) ---

export interface ImmigrationDashboard {
  new_cases: number
  pending_review: number
  high_priority: number
  cleared_cases: number
}

export interface CheckpointBreakdown {
  checkpoint_code: string
  pending: number
  cleared: number
  review_required: number
}

export interface SupervisorDashboard {
  total_scans: number
  pending_cases: number
  review_required: number
  high_priority: number
  active_officers: number
  avg_processing_time_seconds: number | null
  offline_sync_queue: number
  checkpoint_breakdown: CheckpointBreakdown[]
}

export interface AdminDashboard {
  registered_users: number
  registered_devices: number
  sync_queue_pending: number
}

export interface AnalyticsBucket {
  key: string
  count: number
}

export interface AnalyticsDashboard {
  total_screenings: number
  by_document_type: AnalyticsBucket[]
  by_decision: AnalyticsBucket[]
  by_risk_level: AnalyticsBucket[]
  by_day: AnalyticsBucket[]
}

// --- admin (see app/schemas/admin.py) ---

export interface AdminUser {
  id: string
  username: string
  role: Role
  checkpoint_code: string | null
  is_active: boolean
  created_at: string
}

export interface Officer {
  id: string
  username: string
  role: Role
  checkpoint_code: string | null
  is_active: boolean
  case_count: number
}

export interface AdminDevice {
  id: string
  device_identifier: string
  officer_username: string | null
  app_version: string | null
  is_disabled: boolean
  revoked_at: string | null
  revoked_reason: string | null
  last_active_at: string | null
  registered_at: string
}

// --- system (see app/schemas/system.py) ---

export interface SystemHealth {
  api_status: string
  database_status: string
  analysis_pipeline_status: string
  checked_at: string
}

export interface SyncStatus {
  pending: number
  synced: number
  failed: number
  last_successful_sync_at: string | null
}

export interface RiskConfig {
  weights: Record<string, number>
  low_risk_ceiling: number
  medium_risk_ceiling: number
}

// --- testing mode (see app/api/routes/testing.py) ---

export interface TestScenarioSummary {
  id: string
  name: string
  description: string
}

export interface TestScenarioPreview {
  scenario: string
  description: string
  expected_risk_level: string
  expected_issues: string[]
  document_image: string | null
  selfie_image: string | null
  ocr_fields: Record<string, string>
  mrz_text: string | null
}

export interface TestScenarioRunResult {
  scenario: string
  description: string
  designed_to_exercise: {
    expected_risk_level: string
    expected_issues: string[]
  }
  actual_result: ScreeningResponse
}
