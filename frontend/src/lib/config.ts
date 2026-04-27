import { PUBLIC_API_URL } from '$env/static/public'

// Dev  → 'http://localhost:8000'  (cross-origin; FastAPI CORS handles it)
// Prod → ''  (same-origin; ALB routes /api/ and /auth/ to api container)
export const API_BASE_URL: string = PUBLIC_API_URL ?? ''
