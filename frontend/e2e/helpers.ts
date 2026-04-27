import type { Page } from '@playwright/test'

/** Build a valid SSE response body for mocking POST /api/chat. */
export function buildSSEBody(
  tokens: string[],
  graphActions: unknown[],
): string {
  const parts: string[] = []
  for (const token of tokens) {
    parts.push(`event: token\ndata: ${JSON.stringify(token)}\n\n`)
  }
  for (const action of graphActions) {
    parts.push(`event: graph_action\ndata: ${JSON.stringify(action)}\n\n`)
  }
  parts.push('event: done\ndata: {}\n\n')
  return parts.join('')
}

/**
 * Register a fresh user and return their credentials.
 * The backend must be running at http://localhost:8000.
 */
export async function registerUser(
  page: Page,
  opts: { name: string; email: string; password: string },
) {
  await page.goto('/register')
  await page.fill('#name', opts.name)
  await page.fill('#email', opts.email)
  await page.fill('#password', opts.password)
  await page.click('button[type="submit"]')
  // After register, the app redirects to /settings?prompt=api-key
  await page.waitForURL('**/settings**')
}
