import { useQuery } from '@tanstack/react-query'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface HealthResponse {
  status: string
  db: string
  storage: string
}

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`)
  return res.json()
}

function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  })

  const ok = data?.status === 'ok'

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-4 text-xl font-semibold text-gray-900">
          Ledger Extract
        </h1>

        {isLoading && <p className="text-gray-500">Checking health…</p>}

        {isError && (
          <p className="font-medium text-red-600">Unable to reach API</p>
        )}

        {data && (
          <div className="space-y-1">
            <p
              className={`font-medium ${ok ? 'text-green-600' : 'text-red-600'}`}
            >
              status: {data.status}
            </p>
            <p className="text-sm text-gray-600">db: {data.db}</p>
            <p className="text-sm text-gray-600">storage: {data.storage}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
