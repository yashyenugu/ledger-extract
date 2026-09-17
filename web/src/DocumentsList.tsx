import { useQuery } from '@tanstack/react-query'
import { fetchDocuments } from './api'

const STATUS_COLORS: Record<string, string> = {
  UPLOADED: 'bg-gray-100 text-gray-700',
  FAILED: 'bg-red-100 text-red-700',
  APPROVED: 'bg-green-100 text-green-700',
  AUTO_APPROVED: 'bg-green-100 text-green-700',
}

export function DocumentsList() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
    refetchInterval: 2000,
  })

  if (isLoading) {
    return <p className="text-sm text-gray-500">Loading documents…</p>
  }

  if (isError) {
    return <p className="text-sm text-red-600">Unable to load documents</p>
  }

  if (!data || data.items.length === 0) {
    return <p className="text-sm text-gray-500">No documents uploaded yet.</p>
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-xs uppercase text-gray-500">
          <th className="py-2 pr-4">Filename</th>
          <th className="py-2 pr-4">Status</th>
          <th className="py-2 pr-4">Uploaded</th>
          <th className="py-2 pr-4">ID</th>
        </tr>
      </thead>
      <tbody>
        {data.items.map((doc) => (
          <tr key={doc.id} className="border-b border-gray-100">
            <td className="py-2 pr-4 font-medium text-gray-900">
              {doc.filename}
            </td>
            <td className="py-2 pr-4">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  STATUS_COLORS[doc.status] ?? 'bg-yellow-100 text-yellow-700'
                }`}
              >
                {doc.status}
              </span>
            </td>
            <td className="py-2 pr-4 text-gray-500">
              {new Date(doc.created_at).toLocaleString()}
            </td>
            <td className="py-2 pr-4 font-mono text-xs text-gray-400">
              {doc.id}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
