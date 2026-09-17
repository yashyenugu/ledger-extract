import { useQuery } from '@tanstack/react-query'
import { DocumentsList } from './DocumentsList'
import { UploadDropzone } from './UploadDropzone'
import { fetchHealth } from './api'

function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  })

  const ok = data?.status === 'ok'

  return (
    <div className="min-h-screen bg-gray-50 px-6 py-10">
      <div className="mx-auto max-w-3xl space-y-8">
        <header className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">
            Ledger Extract
          </h1>

          {isLoading && <p className="text-sm text-gray-500">Checking health…</p>}
          {isError && (
            <p className="text-sm font-medium text-red-600">
              Unable to reach API
            </p>
          )}
          {data && (
            <p
              className={`text-sm font-medium ${ok ? 'text-green-600' : 'text-red-600'}`}
            >
              status: {data.status} · db: {data.db} · storage: {data.storage}
            </p>
          )}
        </header>

        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">
            Upload a receipt
          </h2>
          <UploadDropzone />
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">
            Documents
          </h2>
          <DocumentsList />
        </section>
      </div>
    </div>
  )
}

export default App
