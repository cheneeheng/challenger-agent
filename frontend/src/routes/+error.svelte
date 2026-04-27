<script lang="ts">
  import { page } from '$app/stores'
  import { goto } from '$app/navigation'
</script>

<svelte:head>
  <title>{$page.status} — IdeaLens</title>
</svelte:head>

<div class="min-h-screen bg-gray-950 text-white flex items-center justify-center flex-col gap-6">
  <div class="text-center">
    <p class="text-7xl font-bold text-gray-700 mb-2">{$page.status}</p>
    <p class="text-xl text-gray-300 mb-1">
      {$page.status === 404 ? 'Page not found' : 'Something went wrong'}
    </p>
    {#if $page.error?.message}
      <p class="text-sm text-gray-500">{$page.error.message}</p>
    {/if}
  </div>
  <button
    onclick={() => goto('/')}
    class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg transition-colors text-sm font-medium"
  >
    Back to dashboard
  </button>
</div>
