declare global {
  namespace App {
    interface Locals {
      user: { id: string; email: string; name: string; has_api_key: boolean } | null
    }
  }
}
export {}
