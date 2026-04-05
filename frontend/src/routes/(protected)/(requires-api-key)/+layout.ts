import { redirect } from '@sveltejs/kit'
import { get } from 'svelte/store'
import { authStore } from '$lib/stores/authStore'

export const ssr = false

export function load() {
  const { user } = get(authStore)
  if (!user?.has_api_key) throw redirect(302, '/settings?prompt=api-key')
}
