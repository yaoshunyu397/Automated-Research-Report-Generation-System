import { useCallback, useState } from 'react'
import type { MouseEvent } from 'react'
import type { ViewerState } from '../types'

type UseFileViewerOptions = {
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
  onError: (message: string) => void
}

export function useFileViewer({ apiFetch, onError }: UseFileViewerOptions) {
  const [viewer, setViewer] = useState<ViewerState | null>(null)
  const [viewerLoading, setViewerLoading] = useState(false)

  const openFileViewer = useCallback(async (type: 'pdf' | 'translation', title: string, url: string, event?: MouseEvent) => {
    event?.preventDefault()
    event?.stopPropagation()
    setViewerLoading(true)
    try {
      const response = await apiFetch(url)
      if (!response.ok) throw new Error(`${type === 'pdf' ? '加载 PDF' : '加载翻译文件'}失败：HTTP ${response.status}`)
      if (type === 'pdf') {
        const blob = await response.blob()
        const objectUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
        setViewer((prev) => {
          if (prev?.objectUrl) URL.revokeObjectURL(prev.objectUrl)
          return { type, title, url: objectUrl, objectUrl }
        })
        return
      }
      const content = await response.text()
      setViewer({ type, title, url, content })
    } catch (e) {
      onError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setViewerLoading(false)
    }
  }, [apiFetch, onError])

  const closeFileViewer = useCallback(() => {
    setViewer((prev) => {
      if (prev?.objectUrl) URL.revokeObjectURL(prev.objectUrl)
      return null
    })
  }, [])

  return { viewer, viewerLoading, openFileViewer, closeFileViewer, setViewer }
}
