import { test, expect } from '@playwright/test'
import { registerUser } from './helpers'

const ts = Date.now()
const EMAIL = `auth-test-${ts}@example.com`
const PASSWORD = 'pw-test-secure-123'
const NAME = 'Auth Test User'

test.describe('authentication', () => {
  test('register redirects to settings with api-key prompt', async ({ page }) => {
    await registerUser(page, { name: NAME, email: EMAIL, password: PASSWORD })
    await expect(page).toHaveURL(/settings\?prompt=api-key/)
    await expect(page.locator('h1:has-text("Settings")')).toBeVisible()
    await expect(page.locator('input[placeholder="sk-ant-..."]')).toBeVisible()
  })

  test('login with valid credentials reaches dashboard', async ({ page }) => {
    // Re-use the account created above by registering once more with a unique email
    const loginEmail = `login-test-${ts}@example.com`
    await registerUser(page, { name: NAME, email: loginEmail, password: PASSWORD })

    // Logout
    await page.goto('/')
    const logoutBtn = page.locator('button:has-text("Logout")').first()
    await logoutBtn.click()
    await page.waitForURL('**/login**')

    // Login
    await page.fill('#email', loginEmail)
    await page.fill('#password', PASSWORD)
    await page.click('button[type="submit"]')

    // No API key → lands on settings (requires-api-key guard redirects)
    // The guard in (requires-api-key)/+layout.ts redirects to settings when has_api_key is false
    await expect(page).toHaveURL(/\/(settings.*|$)/)
  })

  test('logout clears session and redirects to login', async ({ page }) => {
    const logoutEmail = `logout-test-${ts}@example.com`
    await registerUser(page, { name: NAME, email: logoutEmail, password: PASSWORD })

    // Navigate to dashboard area and logout
    await page.goto('/')
    const logoutBtn = page.locator('button:has-text("Logout")').first()
    await logoutBtn.click()
    await page.waitForURL('**/login**')
    await expect(page.locator('h2:has-text("Sign in")')).toBeVisible()

    // Protected route redirects back to login
    await page.goto('/')
    await page.waitForURL('**/login**')
  })

  test('register with duplicate email shows error', async ({ page }) => {
    const dupEmail = `dup-test-${ts}@example.com`
    await registerUser(page, { name: NAME, email: dupEmail, password: PASSWORD })
    // Logout and try to register with the same email
    await page.evaluate(() => localStorage.removeItem('auth'))
    await page.goto('/register')
    await page.fill('#name', NAME)
    await page.fill('#email', dupEmail)
    await page.fill('#password', PASSWORD)
    await page.click('button[type="submit"]')
    // Toast or inline error should mention failure
    await expect(page.locator('[data-sonner-toast]')).toBeVisible({ timeout: 5000 })
  })
})
