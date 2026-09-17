export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface HealthResponse {
  status: string
  db: string
  storage: string
}

export interface DocumentSummary {
  id: string
  filename: string
  sha256: string
  mime_type: string
  page_count: number | null
  source: string | null
  status: string
  failure_reason: string | null
  created_at: string
}

export interface DocumentListResponse {
  items: DocumentSummary[]
  total: number
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`)
  return res.json()
}

export async function fetchDocuments(): Promise<DocumentListResponse> {
  const res = await fetch(`${API_URL}/api/documents`)
  if (!res.ok) {
    throw new Error(`failed to list documents: ${res.status}`)
  }
  return res.json()
}

export async function uploadDocument(file: File): Promise<void> {
  const form = new FormData()
  form.append('file', file)

  const res = await fetch(`${API_URL}/api/documents`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `upload failed: ${res.status}`)
  }
}
