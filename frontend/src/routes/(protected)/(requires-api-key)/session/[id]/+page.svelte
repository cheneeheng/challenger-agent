<script lang="ts">
  import { onDestroy } from 'svelte'
  import { page } from '$app/stores'
  import { goto } from '$app/navigation'
  import { v4 as uuidv4 } from 'uuid'
  import { toast } from 'svelte-sonner'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { chatStore } from '$lib/stores/chatStore'
  import { graphStore } from '$lib/stores/graphStore'
  import { authStore } from '$lib/stores/authStore'
  import { streamChat } from '$lib/services/chatService'
  import { addSystemMessage } from '$lib/services/sessionService'
  import { applyDagreLayout } from '$lib/utils/graphLayout'
  import { checkGraphSize } from '$lib/utils/graphGuards'
  import SplitLayout from '$lib/components/layout/SplitLayout.svelte'
  import AppHeader from '$lib/components/layout/AppHeader.svelte'
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte'
  import GraphPanel from '$lib/components/graph/GraphPanel.svelte'
  import { get } from 'svelte/store'

  const sessionId = $derived($page.params.id)

  let initialMessageSent = false
  let prevSessionId = ''
  let prefillText = $state('')

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

  function handleSystemMessage(msg: string) {
    chatStore.addMessage({ id: uuidv4(), role: 'system', content: msg })
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      addSystemMessage(currentSessionId, msg).catch(() => {
        // non-critical — message already visible in chat UI
      })
    }
  }

  function handleAskClaude(text: string) {
    prefillText = text
  }

  async function sendMessage(text: string) {
    const { isStreaming } = $chatStore
    const { currentSessionId, selectedModel } = $sessionStore
    const { nodes, edges } = $graphStore
    const user = get(authStore).user

    if (isStreaming || !currentSessionId || !text.trim() || !user) return

    const guard = checkGraphSize({ nodes, edges })
    if (!guard.allowed) {
      toast.error(guard.warning ?? 'Graph too large')
      return
    }
    if (guard.warning) {
      toast.warning(guard.warning)
    }

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
            sessionStore.saveGraph()
          },
          onError: (msg) => {
            chatStore.setError(msg)
            chatStore.finalizeMessage()
            toast.error(msg)
          },
          onDone: () => {
            chatStore.finalizeMessage()
            // Re-run Dagre layout after every LLM response
            const { nodes, edges } = get(graphStore)
            if (nodes.length > 0) {
              const laid = applyDagreLayout(nodes, edges)
              graphStore.setGraph({ nodes: laid, edges })
            }
            sessionStore.saveGraph()
          },
        }
      )
    } catch {
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

<svelte:boundary>
  {#snippet failed(error: unknown, reset: () => void)}
    <div class="h-screen flex items-center justify-center bg-gray-950 text-white flex-col gap-4">
      <p class="text-red-400">Something went wrong in the session workspace.</p>
      <p class="text-gray-500 text-sm">{error instanceof Error ? error.message : 'Unknown error'}</p>
      <div class="flex gap-3">
        <button onclick={reset} class="text-sm bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors">
          Try again
        </button>
        <button onclick={() => goto('/')} class="text-sm text-indigo-400 hover:text-indigo-300 px-4 py-2 transition-colors">
          Back to dashboard
        </button>
      </div>
    </div>
  {/snippet}

  <div class="h-screen flex flex-col bg-gray-950 text-white overflow-hidden">
    <AppHeader />

    {#if $sessionStore.isLoading}
      <!-- Loading skeleton -->
      <div class="flex-1 flex overflow-hidden">
        <div class="flex-1 flex flex-col border-r border-gray-800 p-4 gap-3">
          {#each [1, 2, 3] as _}
            <div class="h-12 bg-gray-800 rounded-lg animate-pulse"></div>
          {/each}
        </div>
        <div class="flex-1 bg-gray-900/50 animate-pulse"></div>
      </div>
    {:else}
      <div class="flex-1 overflow-hidden">
        <SplitLayout>
          {#snippet left()}
            <ChatPanel onSend={sendMessage} {prefillText} />
          {/snippet}
          {#snippet right()}
            <GraphPanel onSystemMessage={handleSystemMessage} {handleAskClaude} />
          {/snippet}
        </SplitLayout>
      </div>
    {/if}
  </div>
</svelte:boundary>
