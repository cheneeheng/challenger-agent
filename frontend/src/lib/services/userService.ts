import { apiClient } from './api'
import type { UserResponse } from './authService'

export async function updateProfile(name: string): Promise<UserResponse> {
  const { data } = await apiClient.patch<UserResponse>('/api/users/me', { name })
  return data
}

export async function changePassword(
  current_password: string,
  new_password: string
): Promise<void> {
  await apiClient.post('/api/users/me/password', {
    current_password,
    new_password,
  })
}

export async function setApiKey(api_key: string): Promise<UserResponse> {
  const { data } = await apiClient.post<UserResponse>('/api/users/me/api-key', {
    api_key,
  })
  return data
}

export async function deleteApiKey(): Promise<UserResponse> {
  const { data } = await apiClient.delete<UserResponse>('/api/users/me/api-key')
  return data
}

export async function deleteAccount(password: string): Promise<void> {
  await apiClient.delete('/api/users/me', { data: { password } })
}
