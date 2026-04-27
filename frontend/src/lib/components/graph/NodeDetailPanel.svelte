<script lang="ts">
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { getNodeStyle } from '$lib/utils/graphStyles'
  import { get } from 'svelte/store'
  import { updateGraph } from '$lib/services/sessionService'

  let {
    nodeId,
    onSystemMessage,
    handleAskClaude,
  }: {
    nodeId: string
    onSystemMessage?: (msg: string) => void
    handleAskClaude?: (text: string) => void
  } = $props()

  const node = $derived($graphStore.nodes.find((n) => n.id === nodeId) ?? null)
  const style = $derived(node ? getNodeStyle(node.type) : null)

  let editingContent = $state(false)
  let contentDraft = $state('')

  function startEdit() {
    contentDraft = node?.content ?? ''
    editingContent = true
  }

  function cancelEdit() {
    editingContent = false
  }

  async function saveEdit() {
    if (!node) return
    const prevContent = node.content
    graphStore.updateNode(node.id, { content: contentDraft })
    editingContent = false
    onSystemMessage?.(`[User action: edited node "${node.label}" — content updated]`)
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      const { nodes, edges } = get(graphStore)
      await updateGraph(currentSessionId, { nodes, edges } as Record<string, unknown>)
    }
  }

  function handleDelete() {
    if (!node || node.type === 'root') return
    onSystemMessage?.(`[User action: deleted node "${node.label}"]`)
    graphStore.deleteNode(node.id)
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      const { nodes, edges } = get(graphStore)
      updateGraph(currentSessionId, { nodes, edges } as Record<string, unknown>)
    }
  }

  function handleAskClaudeClick() {
    if (!node) return
    handleAskClaude?.(`Tell me more about: ${node.label}`)
    graphStore.setSelectedNodeId(null)
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') graphStore.setSelectedNodeId(null)
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if node && style}
  <div
    class="absolute right-4 top-4 w-72 z-10 rounded-xl border shadow-xl {style.bg} {style.border} {style.text} p-4"
  >
    <div class="flex items-start justify-between gap-2 mb-3">
      <div>
        <div class="text-[10px] font-semibold uppercase tracking-wider opacity-60">
          {style.label}
        </div>
        <div class="font-semibold text-sm mt-0.5">{node.label}</div>
      </div>
      <button
        onclick={() => graphStore.setSelectedNodeId(null)}
        class="text-xs opacity-60 hover:opacity-100 transition-opacity"
      >
        ✕
      </button>
    </div>

    {#if node.score != null}
      <div class="mb-2 text-xs opacity-75">Feasibility: {node.score}/10</div>
    {/if}

    {#if editingContent}
      <textarea
        bind:value={contentDraft}
        rows={4}
        class="w-full bg-black/30 border border-white/20 rounded px-2 py-1 text-xs text-white resize-none focus:outline-none focus:border-white/50 mb-2"
      ></textarea>
      <div class="flex gap-2">
        <button
          onclick={saveEdit}
          class="text-xs bg-white/20 hover:bg-white/30 px-3 py-1 rounded transition-colors"
        >
          Save
        </button>
        <button
          onclick={cancelEdit}
          class="text-xs opacity-60 hover:opacity-100 px-3 py-1 transition-opacity"
        >
          Cancel
        </button>
      </div>
    {:else}
      <p class="text-xs opacity-80 leading-relaxed mb-3">{node.content}</p>
      <div class="flex flex-wrap gap-2">
        <button
          onclick={startEdit}
          class="text-xs bg-white/10 hover:bg-white/20 px-3 py-1 rounded transition-colors"
        >
          Edit
        </button>
        {#if handleAskClaude}
          <button
            onclick={handleAskClaudeClick}
            class="text-xs bg-white/10 hover:bg-white/20 px-3 py-1 rounded transition-colors"
          >
            Ask Claude
          </button>
        {/if}
        {#if node.type !== 'root'}
          <button
            onclick={handleDelete}
            class="text-xs text-red-300 hover:text-red-200 px-3 py-1 transition-colors"
          >
            Delete
          </button>
        {/if}
      </div>
    {/if}
  </div>
{/if}
