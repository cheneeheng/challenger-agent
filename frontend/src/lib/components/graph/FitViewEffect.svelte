<script lang="ts">
  import { useSvelteFlow } from '@xyflow/svelte'
  import { fitViewSignal } from '$lib/stores/graphStore'

  const { fitView } = useSvelteFlow()

  $effect(() => {
    const _ = $fitViewSignal
    if (_ > 0) fitView({ duration: 400 })
  })
</script>
