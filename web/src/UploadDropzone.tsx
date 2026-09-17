import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { uploadDocument } from './api'

export function UploadDropzone() {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err: Error) => setError(err.message),
  })

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0]
    if (file) mutation.mutate(file)
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          handleFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 bg-white hover:border-gray-400'
        }`}
      >
        <p className="text-sm font-medium text-gray-700">
          Drop a PDF, PNG, or JPEG here, or click to choose a file
        </p>
        <p className="mt-1 text-xs text-gray-400">Up to 20MB</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/png,image/jpeg"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {mutation.isPending && (
        <p className="mt-2 text-sm text-gray-500">Uploading…</p>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}
