<script lang="ts">
  import { Splitpanes, Pane } from 'svelte-splitpanes'

  let { left, right }: { left?: import('svelte').Snippet; right?: import('svelte').Snippet } = $props()
</script>

<Splitpanes class="h-full w-full" theme="default">
  <Pane size={40} minSize={25}>
    <div class="h-full flex flex-col overflow-hidden bg-gray-950">
      {@render left?.()}
    </div>
  </Pane>
  <Pane size={60} minSize={30}>
    <div class="h-full relative bg-gray-950">
      {@render right?.()}
    </div>
  </Pane>
</Splitpanes>
