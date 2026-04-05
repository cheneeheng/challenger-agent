<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { page } from '$app/stores'
  import { goto } from '$app/navigation'
  import { v4 as uuidv4 } from 'uuid'
  import { toast } from 'svelte-sonner'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { chatStore } from '$lib/stores/chatStore'
  import { graphStore } from '$lib/stores/graphStore'
  import { authStore } from '$lib/stores/authStore'
  import { streamChat } from '$lib/services/chatService'
  import { applyDagreLayout } from '$lib/utils/graphLayout'
  import SplitLayout from '$lib/components/layout/SplitLayout.svelte'
  import AppHeader from '$lib/components/layout/AppHeader.svelte'
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte'
  import GraphPanel from '$lib/components/graph/GraphPanel.svelte'
  import { get } from 'svelte/store'

  const sessionId = $derived($page.params.id)

  let initialMessageSent = false
  let prevSessionId = ''

  // Load session when ID changes
  $effect(() => {
    if (sessionId && sessionId !== prevSessionId) {
      prevSessionId = sessionId
      initialMessageSent = false
      graphStore.clearGraph()
      chatStore.clear()
      sessionStore.loadSession(sessionId)
    }
  })

  // Auto-send on fresh session
  $effect(() => {
    const { isLoading, error, currentSession } = $sessionStore
    const messages = $chatStore.messages

    if (error) {
      toast.error(error)
      goto('/')
      return
    }

    if (!isLoading && currentSession && messages.length === 0 && !initialMessageSent) {
      initialMessageSent = true
      sendMessage(currentSession.idea)
    }
  })

  async function sendMessage(text: string) {
    const { isStreaming } = $chatStore
    const { currentSessionId, selectedModel } = $sessionStore
    const { nodes, edges } = $graphStore
    const user = get(authStore).user

    if (isStreaming || !currentSessionId || !text.trim() || !user) return

    const userMsgId = uuidv4()
    chatStore.addMessage({ id: userMsgId, role: 'user', content: text })
    chatStore.setStreaming(true)
    chatStore.setError(null)

    const assistantMsgId = uuidv4()
    chatStore.addMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    })

    try {
      await streamChat(
        currentSessionId,
        text,
        { nodes, edges },
        selectedModel,
        {
          onToken: (chunk) => {
            chatStore.appendToken(chunk)
          },
          onGraphAction: (action) => {
            graphStore.applyGraphActions([action])
            // Auto-layout when first nodes come in
            const currentNodes = get(graphStore).nodes
            if (currentNodes.length > 0 && currentNodes.length <= 5) {
              const laid = applyDagreLayout(currentNodes, get(graphStore).edges)
              graphStore.setGraph({ nodes: laid, edges: get(graphStore).edges })
            }
            sessionStore.saveGraph()
          },
          onError: (msg) => {
            chatStore.setError(msg)
            chatStore.finalizeMessage()
            toast.error(msg)
          },
          onDone: () => {
            chatStore.finalizeMessage()
            sessionStore.saveGraph()
          },
        }
      )
    } catch (err) {
      chatStore.setError('Failed to send message')
      chatStore.finalizeMessage()
    }
  }

  onDestroy(() => {
    // nothing to cancel — fetch-based SSE
  })
</script>

<svelte:head>
  <title>{$sessionStore.currentSession?.name ?? 'Session'} — IdeaLens</title>
</svelte:head>

<div class="h-screen flex flex-col bg-gray-950 text-white overflow-hidden">
  <AppHeader />

  {#if $sessionStore.isLoading}
    <div class="flex-1 flex items-center justify-center">
      <p class="text-gray-500 animate-pulse">Loading session…</p>
    </div>
  {:else}
    <div class="flex-1 overflow-hidden">
      <SplitLayout>
        {#snippet left()}
          <ChatPanel onSend={sendMessage} />
        {/snippet}
        {#snippet right()}
          <GraphPanel />
        {/snippet}
      </SplitLayout>
    </div>
  {/if}
</div>
