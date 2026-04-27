<script lang="ts">
  import { chatStore } from '$lib/stores/chatStore'
  import MessageBubble from './MessageBubble.svelte'
  import ChatInput from './ChatInput.svelte'
  import ModelSelector from './ModelSelector.svelte'

  let { onSend, prefillText = '' }: { onSend: (text: string) => void; prefillText?: string } = $props()

  let messagesEl: HTMLDivElement | undefined = $state()

  // Auto-scroll when messages change
  $effect(() => {
    // Subscribe to messages to trigger this effect
    const _ = $chatStore.messages.length
    if (messagesEl) {
      // Use setTimeout to ensure DOM is updated
      setTimeout(() => {
        messagesEl?.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' })
      }, 0)
    }
  })
</script>

<div class="flex flex-col h-full overflow-hidden">
  <!-- Panel header -->
  <div class="flex items-center justify-between px-4 py-2 border-b border-gray-800 shrink-0">
    <span class="font-semibold text-sm text-gray-300">Analysis Chat</span>
    <ModelSelector />
  </div>

  <!-- Messages -->
  <div bind:this={messagesEl} class="flex-1 overflow-y-auto p-4 space-y-3">
    {#if $chatStore.messages.length === 0}
      <p class="text-center text-gray-600 text-sm mt-16">
        Describe your idea to begin the analysis
      </p>
    {/if}

    {#each $chatStore.messages as message (message.id)}
      <MessageBubble {message} />
    {/each}

    {#if $chatStore.isStreaming && $chatStore.messages.at(-1)?.role !== 'assistant'}
      <div class="flex gap-1 px-4 py-2">
        <span
          class="w-2 h-2 rounded-full bg-gray-500 animate-bounce"
          style="animation-delay: -0.3s"
        ></span>
        <span
          class="w-2 h-2 rounded-full bg-gray-500 animate-bounce"
          style="animation-delay: -0.15s"
        ></span>
        <span class="w-2 h-2 rounded-full bg-gray-500 animate-bounce"></span>
      </div>
    {/if}

    {#if $chatStore.error}
      <div class="bg-red-900/40 border border-red-700 rounded-lg px-4 py-2 text-red-300 text-sm">
        {$chatStore.error}
      </div>
    {/if}
  </div>

  <!-- Input -->
  <div class="shrink-0">
    <ChatInput disabled={$chatStore.isStreaming} {onSend} {prefillText} />
  </div>
</div>
