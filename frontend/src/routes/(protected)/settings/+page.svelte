<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { toast } from 'svelte-sonner'
  import { authStore } from '$lib/stores/authStore'
  import {
    updateProfile,
    changePassword,
    setApiKey,
    deleteApiKey,
    deleteAccount,
  } from '$lib/services/userService'
  import { logout } from '$lib/services/authService'

  const user = $derived($authStore.user)
  const promptApiKey = $derived($page.url.searchParams.get('prompt') === 'api-key')

  let name = $state($authStore.user?.name ?? '')
  let profileLoading = $state(false)

  let currentPassword = $state('')
  let newPassword = $state('')
  let passwordLoading = $state(false)

  let apiKey = $state('')
  let apiKeyLoading = $state(false)

  let deletePassword = $state('')
  let showDeleteConfirm = $state(false)
  let deleteLoading = $state(false)

  async function saveProfile() {
    profileLoading = true
    try {
      const updated = await updateProfile(name)
      authStore.updateUser(updated)
      toast.success('Profile updated')
    } catch {
      toast.error('Failed to update profile')
    } finally {
      profileLoading = false
    }
  }

  async function savePassword() {
    if (newPassword.length < 8) {
      toast.error('New password must be at least 8 characters')
      return
    }
    passwordLoading = true
    try {
      await changePassword(currentPassword, newPassword)
      currentPassword = ''
      newPassword = ''
      toast.success('Password changed')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Failed to change password'
      toast.error(msg)
    } finally {
      passwordLoading = false
    }
  }

  async function saveApiKey() {
    if (!apiKey.startsWith('sk-ant-')) {
      toast.error("API key must start with 'sk-ant-'")
      return
    }
    apiKeyLoading = true
    try {
      const updated = await setApiKey(apiKey)
      authStore.updateUser(updated)
      apiKey = ''
      toast.success('API key saved and validated')
      if (promptApiKey) goto('/')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Failed to save API key'
      toast.error(msg)
    } finally {
      apiKeyLoading = false
    }
  }

  async function removeApiKey() {
    try {
      const updated = await deleteApiKey()
      authStore.updateUser(updated)
      toast.success('API key removed')
    } catch {
      toast.error('Failed to remove API key')
    }
  }

  async function handleDeleteAccount() {
    deleteLoading = true
    try {
      await deleteAccount(deletePassword)
      await logout()
      authStore.logout()
      goto('/login')
      toast.success('Account deleted')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Failed to delete account'
      toast.error(msg)
    } finally {
      deleteLoading = false
    }
  }

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // ignore
    }
    authStore.logout()
    goto('/login')
  }
</script>

<svelte:head>
  <title>Settings — IdeaLens</title>
</svelte:head>

<div class="min-h-screen bg-gray-950 text-white">
  <!-- Header -->
  <header class="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-4">
      <a href="/" class="text-gray-400 hover:text-white transition-colors text-sm">← Dashboard</a>
      <h1 class="text-xl font-semibold">Settings</h1>
    </div>
    <button
      onclick={handleLogout}
      class="text-sm text-gray-400 hover:text-white transition-colors"
    >
      Sign out
    </button>
  </header>

  <div class="max-w-2xl mx-auto px-6 py-10 space-y-8">
    {#if promptApiKey}
      <div class="bg-yellow-900/40 border border-yellow-600 rounded-lg p-4 text-yellow-200 text-sm">
        Please add your Anthropic API key to start analyzing ideas.
      </div>
    {/if}

    <!-- Profile -->
    <section class="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h2 class="text-lg font-semibold mb-4">Profile</h2>
      <div class="space-y-3">
        <div>
          <label for="profile-name" class="block text-sm text-gray-400 mb-1">Name</label>
          <input
            id="profile-name"
            type="text"
            bind:value={name}
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div>
          <label for="profile-email" class="block text-sm text-gray-400 mb-1">Email</label>
          <input
            id="profile-email"
            type="email"
            value={user?.email ?? ''}
            disabled
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-500 cursor-not-allowed"
          />
        </div>
        <button
          onclick={saveProfile}
          disabled={profileLoading}
          class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {profileLoading ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </section>

    <!-- API Key -->
    <section class="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h2 class="text-lg font-semibold mb-1">Anthropic API Key</h2>
      <p class="text-sm text-gray-500 mb-4">
        Your key is encrypted at rest and never returned in plaintext.
        Get yours at <a href="https://console.anthropic.com" class="text-indigo-400 hover:text-indigo-300" target="_blank" rel="noopener">console.anthropic.com</a>.
      </p>

      {#if user?.has_api_key}
        <div class="flex items-center gap-3 mb-4">
          <span class="text-green-400 text-sm">API key is set</span>
          <button
            onclick={removeApiKey}
            class="text-sm text-red-400 hover:text-red-300 transition-colors"
          >
            Remove
          </button>
        </div>
      {/if}

      <div class="flex gap-2">
        <input
          type="password"
          bind:value={apiKey}
          placeholder="sk-ant-..."
          class="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          onclick={saveApiKey}
          disabled={apiKeyLoading || !apiKey}
          class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {apiKeyLoading ? 'Validating…' : user?.has_api_key ? 'Update' : 'Save'}
        </button>
      </div>
    </section>

    <!-- Change Password -->
    <section class="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h2 class="text-lg font-semibold mb-4">Change Password</h2>
      <div class="space-y-3">
        <div>
          <label for="current-password" class="block text-sm text-gray-400 mb-1">Current password</label>
          <input
            id="current-password"
            type="password"
            bind:value={currentPassword}
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div>
          <label for="new-password" class="block text-sm text-gray-400 mb-1">New password</label>
          <input
            id="new-password"
            type="password"
            bind:value={newPassword}
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          onclick={savePassword}
          disabled={passwordLoading || !currentPassword || !newPassword}
          class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {passwordLoading ? 'Updating…' : 'Update password'}
        </button>
      </div>
    </section>

    <!-- Danger Zone -->
    <section class="bg-gray-900 border border-red-900 rounded-xl p-6">
      <h2 class="text-lg font-semibold text-red-400 mb-2">Danger Zone</h2>
      <p class="text-sm text-gray-500 mb-4">
        Permanently delete your account and all data. This cannot be undone.
      </p>

      {#if !showDeleteConfirm}
        <button
          onclick={() => (showDeleteConfirm = true)}
          class="text-sm text-red-400 border border-red-800 hover:bg-red-900/40 px-4 py-2 rounded-lg transition-colors"
        >
          Delete account
        </button>
      {:else}
        <div class="space-y-3">
          <p class="text-sm text-red-400">Enter your password to confirm deletion:</p>
          <input
            type="password"
            bind:value={deletePassword}
            placeholder="Your password"
            class="w-full bg-gray-800 border border-red-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-red-500"
          />
          <div class="flex gap-2">
            <button
              onclick={handleDeleteAccount}
              disabled={deleteLoading || !deletePassword}
              class="bg-red-700 hover:bg-red-800 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {deleteLoading ? 'Deleting…' : 'Confirm delete'}
            </button>
            <button
              onclick={() => { showDeleteConfirm = false; deletePassword = '' }}
              class="text-sm text-gray-400 hover:text-white px-4 py-2 rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      {/if}
    </section>
  </div>
</div>
