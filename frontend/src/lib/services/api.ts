import axios from 'axios'
import { API_BASE_URL } from '$lib/config'
import { authStore } from '$lib/stores/authStore'
import { get } from 'svelte/store'
import { goto } from '$app/navigation'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

apiClient.interceptors.request.use((config) => {
  const { accessToken } = get(authStore)
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

let isRefreshing = false
let queue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        queue.push({
          resolve: (token) => {
            original.headers.Authorization = `Bearer ${token}`
            resolve(apiClient(original))
          },
          reject,
        })
      })
    }

    original._retry = true
    isRefreshing = true
    try {
      const resp = await apiClient.post('/auth/refresh')
      const token = resp.data.access_token
      authStore.setAccessToken(token)
      queue.forEach((q) => q.resolve(token))
      queue = []
      original.headers.Authorization = `Bearer ${token}`
      return apiClient(original)
    } catch (e) {
      queue.forEach((q) => q.reject(e))
      queue = []
      authStore.logout()
      goto('/login')
      return Promise.reject(e)
    } finally {
      isRefreshing = false
    }
  }
)
