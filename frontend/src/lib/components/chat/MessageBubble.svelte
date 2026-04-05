<script lang="ts">
  import type { ChatMessage } from '$lib/stores/chatStore'

  let { message }: { message: ChatMessage } = $props()
</script>

{#if message.role === 'system'}
  <div class="flex justify-center my-1 px-4">
    <span class="text-xs text-gray-500 italic bg-gray-800 px-3 py-0.5 rounded-full">
      {message.content}
    </span>
  </div>
{:else if message.role === 'user'}
  <div class="flex justify-end">
    <div class="max-w-[80%] rounded-2xl rounded-tr-sm bg-indigo-700 text-white px-4 py-2 text-sm whitespace-pre-wrap">
      {message.content}
    </div>
  </div>
{:else}
  <div class="flex gap-2">
    <div
      class="w-7 h-7 rounded-full bg-gray-700 border border-gray-600 flex items-center justify-center text-xs font-bold shrink-0 text-indigo-300"
    >
      AI
    </div>
    <div class="max-w-[80%] rounded-2xl rounded-tl-sm bg-gray-800 text-gray-100 px-4 py-2 text-sm whitespace-pre-wrap">
      {message.content}
      {#if message.isStreaming}
        <span class="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse align-middle"></span>
      {/if}
    </div>
  </div>
{/if}
