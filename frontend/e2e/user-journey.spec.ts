/**
 * Full happy-path user journey:
 *   register → set API key → new analysis → graph → follow-up → edit node → settings → delete account
 *
 * The Anthropic API validation (POST /api/users/me/api-key) and
 * LLM chat streaming (POST /api/chat) are mocked at the network level
 * so the test runs without a real Anthropic key.
 *
 * Prerequisites: backend running at http://localhost:8000 with a live PostgreSQL connection.
 */
import { test, expect } from '@playwright/test'
import { registerUser, buildSSEBody } from './helpers'

const ts = Date.now()
const EMAIL = `journey-${ts}@example.com`
const PASSWORD = 'journey-password-123'
const NAME = 'Journey Test'
const IDEA = 'A marketplace for local handmade goods connecting artisans with buyers'

// First SSE response: initial analysis adds two nodes
const INITIAL_SSE = buildSSEBody(
  ['This', ' is', ' a', ' great', ' concept!'],
  [
    {
      action: 'add',
      payload: {
        id: 'benefit-1',
        type: 'benefit',
        label: 'Supports local economy',
        content: 'Enables artisans to sell directly, keeping money in the community.',
        score: null,
        parent_id: 'root',
      },
    },
    {
      action: 'connect',
      payload: { source: 'root', target: 'benefit-1', label: 'has benefit' },
    },
    {
      action: 'add',
      payload: {
        id: 'requirement-1',
        type: 'requirement',
        label: 'Payment processing',
        content: 'Secure payment gateway integration.',
        score: null,
        parent_id: 'root',
      },
    },
    {
      action: 'connect',
      payload: { source: 'root', target: 'requirement-1', label: 'requires' },
    },
  ],
)

// Second SSE response: follow-up adds a challenge node
const FOLLOWUP_SSE = buildSSEBody(
  ['The', ' main', ' challenge', ' is', ' trust.'],
  [
    {
      action: 'add',
      payload: {
        id: 'drawback-1',
        type: 'drawback',
        label: 'Trust and verification',
        content: 'Buyers need confidence in seller quality before purchasing.',
        score: null,
        parent_id: 'root',
      },
    },
    {
      action: 'connect',
      payload: { source: 'root', target: 'drawback-1', label: 'challenged by' },
    },
  ],
)

test('register → API key → analyze → follow-up → edit node → settings → delete account', async ({
  page,
}) => {
  // ── 1. Register ────────────────────────────────────────────────────────────
  await registerUser(page, { name: NAME, email: EMAIL, password: PASSWORD })
  await expect(page.locator('h1:has-text("Settings")')).toBeVisible()

  // ── 2. Set API key (mock Anthropic validation) ─────────────────────────────
  await page.route('**/api/users/me/api-key', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      // Minimal partial — authStore.updateUser() merges this into the real user object
      body: JSON.stringify({ has_api_key: true }),
    })
  })

  await page.fill('input[placeholder="sk-ant-..."]', 'sk-ant-mock-key-playwright-test')
  await page.click('button:has-text("Save")')
  await page.waitForURL('**/')
  await expect(page).toHaveURL('/')

  // ── 3. New Analysis modal ──────────────────────────────────────────────────
  await page.click('button:has-text("New Analysis")')
  await expect(page.locator('#new-idea')).toBeVisible()
  await page.fill('#new-idea', IDEA)

  // ── 4. Mock chat endpoint (handles both initial auto-send and follow-up) ───
  let chatCall = 0
  await page.route('**/api/chat', (route) => {
    chatCall++
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' },
      body: chatCall === 1 ? INITIAL_SSE : FOLLOWUP_SSE,
    })
  })

  await page.click('button:has-text("Analyze")')
  await page.waitForURL('**/session/**', { timeout: 10_000 })

  // ── 5. Verify graph populates (root + 2 new nodes = 3 total) ──────────────
  // The initial SSE fires automatically on session mount; wait for nodes
  await expect(page.locator('.svelte-flow__node')).toHaveCount(3, { timeout: 15_000 })

  // Chat panel shows assistant response
  await expect(page.locator('text=This')).toBeVisible({ timeout: 8_000 })

  // ── 6. Send follow-up message ─────────────────────────────────────────────
  const chatTextarea = page.locator('form textarea')
  await chatTextarea.waitFor({ state: 'visible' })
  // Wait until the textarea is enabled (streaming complete)
  await expect(chatTextarea).not.toBeDisabled({ timeout: 12_000 })
  await chatTextarea.fill('What are the main challenges for this idea?')
  await page.keyboard.press('Enter')
  // Wait for the follow-up SSE to complete
  await expect(page.locator('.svelte-flow__node')).toHaveCount(4, { timeout: 15_000 })

  // ── 7. Click a node to open NodeDetailPanel ───────────────────────────────
  // Click the benefit node (second node, after root)
  const benefitNode = page.locator('.svelte-flow__node').nth(1)
  await benefitNode.click()
  await expect(page.locator('button:has-text("Edit")')).toBeVisible({ timeout: 5_000 })

  // ── 8. Edit node content ──────────────────────────────────────────────────
  await page.click('button:has-text("Edit")')
  const contentArea = page.locator('.absolute.right-4 textarea')
  await expect(contentArea).toBeVisible()
  await contentArea.fill('Updated: Artisans retain more of their revenue by selling direct.')
  await page.click('button:has-text("Save")')
  // Panel stays visible in view mode after save
  await expect(page.locator('button:has-text("Edit")')).toBeVisible({ timeout: 5_000 })

  // ── 9. Navigate to settings via header link ────────────────────────────────
  await page.click('a[href="/settings"]')
  await page.waitForURL('**/settings**')
  await expect(page.locator('h1:has-text("Settings")')).toBeVisible()

  // ── 10. Delete account ────────────────────────────────────────────────────
  await page.click('button:has-text("Delete account")')
  await expect(page.locator('input[placeholder="Your password"]')).toBeVisible()
  await page.fill('input[placeholder="Your password"]', PASSWORD)
  await page.click('button:has-text("Confirm delete")')
  await page.waitForURL('**/login**', { timeout: 10_000 })
  await expect(page.locator('h2:has-text("Sign in")')).toBeVisible()
})
