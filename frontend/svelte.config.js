import adapterNode from '@sveltejs/adapter-node'
import adapterVercel from '@sveltejs/adapter-vercel'
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'

// Set ADAPTER=vercel in the Vercel build environment.
// All other environments (Docker, local) fall back to adapter-node.
const adapter =
  process.env.ADAPTER === 'vercel' ? adapterVercel() : adapterNode()

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: { adapter },
}
export default config
