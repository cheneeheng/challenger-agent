import { apiClient } from './api'

export interface SessionListItem {
  id: string
  name: string
  idea: string
  selected_model: string
  updated_at: string
  created_at: string
}

export interface SessionResponse {
  id: string
  name: string
  idea: string
  selected_model: string
  graph_state: Record<string, unknown>
  context_summary: string | null
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  items: SessionListItem[]
  total: number
  page: number
  limit: number
}

export async function listSessions(
  page = 1,
  limit = 20
): Promise<SessionListResponse> {
  const { data } = await apiClient.get<SessionListResponse>('/api/sessions', {
    params: { page, limit },
  })
  return data
}

export async function createSession(
  idea: string,
  selected_model: string
): Promise<SessionResponse> {
  const { data } = await apiClient.post<SessionResponse>('/api/sessions', {
    idea,
    selected_model,
  })
  return data
}

export async function getSession(id: string): Promise<SessionResponse> {
  const { data } = await apiClient.get<SessionResponse>(`/api/sessions/${id}`)
  return data
}

export async function updateSession(
  id: string,
  changes: { name?: string; selected_model?: string }
): Promise<SessionResponse> {
  const { data } = await apiClient.patch<SessionResponse>(
    `/api/sessions/${id}`,
    changes
  )
  return data
}

export async function deleteSession(id: string): Promise<void> {
  await apiClient.delete(`/api/sessions/${id}`)
}

export async function updateGraph(
  id: string,
  graph_state: Record<string, unknown>
): Promise<void> {
  await apiClient.put(`/api/sessions/${id}/graph`, { graph_state })
}

export async function addSystemMessage(
  sessionId: string,
  content: string
): Promise<void> {
  await apiClient.post(`/api/sessions/${sessionId}/messages`, {
    role: 'system',
    content,
  })
}
