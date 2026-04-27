<script lang="ts">
  import '../app.css'
  import { onMount } from 'svelte'
  import { Toaster } from 'svelte-sonner'
  import { authStore } from '$lib/stores/authStore'

  let { children } = $props()

  onMount(() => {
    authStore.init()
  })
</script>

{@render children()}
<Toaster position="bottom-right" richColors />
