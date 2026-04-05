import { redirect } from '@sveltejs/kit'
import { get } from 'svelte/store'
import { authStore } from '$lib/stores/authStore'

export const ssr = false

export function load() {
  const { user, accessToken } = get(authStore)
  if (!user || !accessToken) throw redirect(302, '/login')
}
