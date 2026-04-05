<script lang="ts">
  let {
    disabled = false,
    onSend,
  }: { disabled?: boolean; onSend: (text: string) => void } = $props()

  let input = $state('')

  function handleSubmit(e: SubmitEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || disabled) return
    onSend(text)
    input = ''
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const text = input.trim()
      if (text && !disabled) {
        onSend(text)
        input = ''
      }
    }
  }
</script>

<form onsubmit={handleSubmit} class="border-t border-gray-800 p-3 flex gap-2">
  <textarea
    bind:value={input}
    onkeydown={handleKeydown}
    {disabled}
    placeholder={disabled ? 'Waiting for response…' : 'Ask a follow-up question…'}
    rows={2}
    class="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none disabled:opacity-50"
  ></textarea>
  <button
    type="submit"
    disabled={disabled || !input.trim()}
    class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors self-end"
  >
    Send
  </button>
</form>
