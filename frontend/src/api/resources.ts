import { apiClient } from './client'
import type {
  AdminDashboard,
  AdminDevice,
  AdminUser,
  AnalyticsDashboard,
  AuditEvent,
  AuditLogEntry,
  CaseDetail,
  CaseListItem,
  CaseStatus,
  Checkpoint,
  CurrentUser,
  DecisionValue,
  IdentityHistoryRecord,
  ImmigrationDashboard,
  LoginResponse,
  NetworkGraph,
  Officer,
  PersonSearchResult,
  RegistryLookupResult,
  RelationshipListItem,
  RiskConfig,
  SupervisorDashboard,
  SyncStatus,
  SystemHealth,
  TestScenarioPreview,
  TestScenarioRunResult,
  TestScenarioSummary,
  TimelineEvent,
} from './types'

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', { username, password })
  return data
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const { data } = await apiClient.get<CurrentUser>('/auth/me')
  return data
}

export async function listCheckpoints(): Promise<Checkpoint[]> {
  const { data } = await apiClient.get<Checkpoint[]>('/checkpoints')
  return data
}

export interface CaseFilters {
  status_filter?: CaseStatus
  checkpoint_id?: string
  priority?: string
  limit?: number
}

export async function listCases(filters: CaseFilters = {}): Promise<CaseListItem[]> {
  const { data } = await apiClient.get<CaseListItem[]>('/cases', { params: filters })
  return data
}

export async function getCase(caseId: string): Promise<CaseDetail> {
  const { data } = await apiClient.get<CaseDetail>(`/cases/${caseId}`)
  return data
}

export async function submitCase(caseId: string, note?: string): Promise<CaseListItem> {
  const { data } = await apiClient.post<CaseListItem>(`/cases/${caseId}/submit`, { note })
  return data
}

export async function decideCase(caseId: string, decision: DecisionValue, reason?: string): Promise<CaseDetail> {
  const { data } = await apiClient.post<CaseDetail>(`/cases/${caseId}/decision`, { decision, reason })
  return data
}

export async function addCaseNote(caseId: string, note: string) {
  const { data } = await apiClient.post(`/cases/${caseId}/notes`, { note })
  return data
}

export async function getCaseAudit(caseId: string): Promise<AuditEvent[]> {
  const { data } = await apiClient.get<AuditEvent[]>(`/cases/${caseId}/audit`)
  return data
}

export async function getCaseTimeline(caseId: string): Promise<TimelineEvent[]> {
  const { data } = await apiClient.get<TimelineEvent[]>(`/cases/${caseId}/timeline`)
  return data
}

export async function getCaseIdentityHistory(caseId: string): Promise<IdentityHistoryRecord[]> {
  const { data } = await apiClient.get<IdentityHistoryRecord[]>(`/cases/${caseId}/identity-history`)
  return data
}

export async function getCaseNetworkGraph(caseId: string): Promise<NetworkGraph> {
  const { data } = await apiClient.get<NetworkGraph>(`/network/cases/${caseId}`)
  return data
}

export async function expandEntity(entityId: string, entityType: string): Promise<NetworkGraph> {
  const { data } = await apiClient.get<NetworkGraph>(`/network/entities/${entityId}`, {
    params: { entity_type: entityType },
  })
  return data
}

export async function listRelationships(params: {
  checkpoint_id?: string
  relationship_type?: string
}): Promise<RelationshipListItem[]> {
  const { data } = await apiClient.get<RelationshipListItem[]>('/network/relationships', { params })
  return data
}

export async function searchPersons(q: string): Promise<PersonSearchResult[]> {
  const { data } = await apiClient.get<PersonSearchResult[]>('/network/persons/search', { params: { q } })
  return data
}

export async function getImmigrationDashboard(): Promise<ImmigrationDashboard> {
  const { data } = await apiClient.get<ImmigrationDashboard>('/dashboard/immigration')
  return data
}

export async function getSupervisorDashboard(): Promise<SupervisorDashboard> {
  const { data } = await apiClient.get<SupervisorDashboard>('/dashboard/supervisor')
  return data
}

export async function getAdminDashboard(): Promise<AdminDashboard> {
  const { data } = await apiClient.get<AdminDashboard>('/dashboard/admin')
  return data
}

export async function getAnalyticsDashboard(days = 14): Promise<AnalyticsDashboard> {
  const { data } = await apiClient.get<AnalyticsDashboard>('/dashboard/analytics', { params: { days } })
  return data
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  const { data } = await apiClient.get<AdminUser[]>('/admin/users')
  return data
}

export async function createAdminUser(payload: {
  username: string
  password: string
  role: string
  checkpoint_id?: string | null
}): Promise<AdminUser> {
  const { data } = await apiClient.post<AdminUser>('/admin/users', payload)
  return data
}

export async function updateAdminUser(
  userId: string,
  payload: Partial<{ role: string; checkpoint_id: string; is_active: boolean; new_password: string }>,
): Promise<AdminUser> {
  const { data } = await apiClient.patch<AdminUser>(`/admin/users/${userId}`, payload)
  return data
}

export async function listAdminDevices(): Promise<AdminDevice[]> {
  const { data } = await apiClient.get<AdminDevice[]>('/admin/devices')
  return data
}

export async function setDeviceDisabled(deviceId: string, isDisabled: boolean): Promise<AdminDevice> {
  const { data } = await apiClient.patch<AdminDevice>(`/admin/devices/${deviceId}`, { is_disabled: isDisabled })
  return data
}

export async function revokeDevice(deviceId: string, reason: string): Promise<AdminDevice> {
  const { data } = await apiClient.post<AdminDevice>(`/admin/devices/${deviceId}/revoke`, { reason })
  return data
}

export async function reactivateDevice(deviceId: string): Promise<AdminDevice> {
  const { data } = await apiClient.post<AdminDevice>(`/admin/devices/${deviceId}/reactivate`)
  return data
}

export async function listAdminCheckpoints(): Promise<Checkpoint[]> {
  const { data } = await apiClient.get<Checkpoint[]>('/admin/checkpoints')
  return data
}

export async function listOfficers(): Promise<Officer[]> {
  const { data } = await apiClient.get<Officer[]>('/admin/officers')
  return data
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const { data } = await apiClient.get<SystemHealth>('/system/health')
  return data
}

export async function getSyncStatus(): Promise<SyncStatus> {
  const { data } = await apiClient.get<SyncStatus>('/system/sync-status')
  return data
}

export async function getRiskConfig(): Promise<RiskConfig> {
  const { data } = await apiClient.get<RiskConfig>('/system/risk-config')
  return data
}

export async function listTestScenarios(): Promise<TestScenarioSummary[]> {
  const { data } = await apiClient.get<{ scenarios: TestScenarioSummary[] }>('/testing/scenarios')
  return data.scenarios
}

export async function previewTestScenario(scenario: string): Promise<TestScenarioPreview> {
  const { data } = await apiClient.post<TestScenarioPreview>('/testing/generate', { scenario })
  return data
}

export async function runTestScenario(scenario: string): Promise<TestScenarioRunResult> {
  const { data } = await apiClient.post<TestScenarioRunResult>('/testing/submit-screening', { scenario })
  return data
}

export async function listAuditLogs(limit = 100): Promise<AuditLogEntry[]> {
  const { data } = await apiClient.get<AuditLogEntry[]>('/audit-logs', { params: { limit } })
  return data
}

export async function seedMockRegistry(): Promise<{ seeded: number }> {
  const { data } = await apiClient.post<{ seeded: number }>('/registry/seed', {})
  return data
}

export async function lookupRegistry(params: {
  document_number?: string
  name?: string
}): Promise<RegistryLookupResult> {
  const { data } = await apiClient.post<RegistryLookupResult>('/registry/lookup', params)
  return data
}
