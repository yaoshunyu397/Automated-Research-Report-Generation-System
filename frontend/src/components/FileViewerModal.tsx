import type { ViewerState } from '../types'

type FileViewerModalProps = {
  viewer: ViewerState | null
  viewerLoading: boolean
  onClose: () => void
}

export function FileViewerModal({ viewer, viewerLoading, onClose }: FileViewerModalProps) {
  if (!viewer) return null

  return (
    <div className="viewerBackdrop" role="dialog" aria-modal="true">
      <div className="viewerPanel">
        <div className="viewerHead">
          <div className="viewerTitle">{viewer.title}</div>
          <button className="btn" onClick={onClose}>关闭</button>
        </div>
        <div className="viewerBody">
          {viewerLoading ? <div className="empty">正在加载文件...</div> : null}
          {!viewerLoading && viewer.type === 'pdf' && viewer.url ? (
            <iframe className="pdfFrame" src={viewer.url} title={viewer.title} />
          ) : null}
          {!viewerLoading && viewer.type === 'translation' ? (
            <pre className="translationPreview">{viewer.content || '（翻译文件为空）'}</pre>
          ) : null}
          {!viewerLoading && viewer.type === 'report' ? (
            <pre className="reportPreview">{viewer.content || '（报告内容为空）'}</pre>
          ) : null}
        </div>
      </div>
    </div>
  )
}
