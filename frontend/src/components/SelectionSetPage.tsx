import type { MouseEvent } from 'react'
import type { ArxivItem, ExistingReport, ExistingSelectionSet } from '../types'

type SelectionSetPageProps = {
  error: string | null
  existingSets: ExistingSelectionSet[]
  visibleSelectionSets: ExistingSelectionSet[]
  selectionFilter: string
  selectionSort: 'newest' | 'oldest' | 'name' | 'count'
  expandedSetId: number | null
  existingSetDetails: Record<number, ArxivItem[]>
  existingSetReports: Record<number, ExistingReport[]>
  onRefresh: () => void
  onBackToSearch: () => void
  onSelectionFilterChange: (value: string) => void
  onSelectionSortChange: (value: 'newest' | 'oldest' | 'name' | 'count') => void
  onToggleSet: (selectionSetId: number) => void
  onDeleteSet: (selectionSetId: number) => void
  onLoadSelectionSetToSearch: (selectionSetId: number) => void
  onPreviewReport: (reportId: number) => void
  onLoadReport: (selectionSetId: number, name: string, count: number, reportId: number, query?: string | null) => void
  onDeleteReport: (selectionSetId: number, reportId: number) => void
  onOpenFileViewer: (type: 'pdf' | 'translation', title: string, url: string, event?: MouseEvent) => void
}

export function SelectionSetPage({
  error,
  existingSets,
  visibleSelectionSets,
  selectionFilter,
  selectionSort,
  expandedSetId,
  existingSetDetails,
  existingSetReports,
  onRefresh,
  onBackToSearch,
  onSelectionFilterChange,
  onSelectionSortChange,
  onToggleSet,
  onDeleteSet,
  onLoadSelectionSetToSearch,
  onPreviewReport,
  onLoadReport,
  onDeleteReport,
  onOpenFileViewer,
}: SelectionSetPageProps) {
  return (
    <div className="page">
      <div className="panel selectionSetsPanel">
        <div className="panelHead">
          <h2>参考文献选择集 {existingSets.length > 0 && <span className="countBadge">{existingSets.length}</span>}</h2>
          <div className="right">
            <button className="btn" onClick={onRefresh}>刷新</button>
            <button className="btn primary" onClick={onBackToSearch}>前往论文检索</button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        <div className="selectionToolbar">
          <input
            className="input"
            value={selectionFilter}
            onChange={(e) => onSelectionFilterChange(e.target.value)}
            placeholder="按选择集名称或检索关键词筛选"
          />
          <select className="input small" value={selectionSort} onChange={(e) => onSelectionSortChange(e.target.value as SelectionSetPageProps['selectionSort'])}>
            <option value="newest">最新创建优先</option>
            <option value="oldest">最早创建优先</option>
            <option value="name">按名称排序</option>
            <option value="count">按论文数量排序</option>
          </select>
          <span className="muted">显示 {visibleSelectionSets.length}/{existingSets.length} 个选择集</span>
        </div>
        <div className="existingSetsWrap">
          {visibleSelectionSets.length === 0 ? (
            <div className="empty">没有匹配的参考文献选择集。可以调整筛选条件，或先进入论文检索模块保存选择。</div>
          ) : (
            visibleSelectionSets.map((item) => (
              <div key={item.selection_set_id} className="existingSetCard">
                <button className="existingSetHead" onClick={() => onToggleSet(item.selection_set_id)}>
                  <span><b>{item.name}</b>（{item.query || '未记录关键词'}）（{item.count} 篇）</span>
                  <span>{expandedSetId === item.selection_set_id ? '收起' : '展开'}</span>
                </button>
                <div className="existingSetActions">
                  <button className="btn primary" onClick={() => onLoadSelectionSetToSearch(item.selection_set_id)}>
                    加载到检索
                  </button>
                  <button className="btn danger" onClick={() => onDeleteSet(item.selection_set_id)}>
                    删除选择集
                  </button>
                </div>
                {expandedSetId === item.selection_set_id && (
                  <div className="existingSetBody">
                    <div className="savedReportsBlock">
                      <div className="savedReportsTitle">已保存报告</div>
                      {(existingSetReports[item.selection_set_id] ?? []).length === 0 ? (
                        <div className="muted compactMuted">暂无已保存报告。</div>
                      ) : (
                        (existingSetReports[item.selection_set_id] ?? []).map((report) => (
                          <div key={report.report_id} className="savedReportRow">
                            <div>
                              <div className="savedReportTitle">{item.query || item.name || '调研'}调研报告</div>
                              <div className="savedReportMeta">
                                {report.filled_section_count}/{report.section_count} 个章节已有内容
                                {report.updated_at ? ` · 更新于 ${new Date(report.updated_at).toLocaleString()}` : ''}
                              </div>
                            </div>
                            <div className="savedReportActions">
                              <button className="btn" onClick={() => onPreviewReport(report.report_id)}>网页查看</button>
                              <button className="btn primary" onClick={() => onLoadReport(item.selection_set_id, item.name, item.count, report.report_id, item.query)}>加载编辑</button>
                              <button className="btn danger" onClick={() => onDeleteReport(item.selection_set_id, report.report_id)}>删除</button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="savedReportsTitle paperListTitle">选择集论文</div>
                    {(existingSetDetails[item.selection_set_id] ?? []).length === 0 ? (
                      <div className="muted">暂无论文数据或正在加载。</div>
                    ) : (
                      (existingSetDetails[item.selection_set_id] ?? []).map((paper) => (
                        <div key={paper.arxiv_id} className="existingPaperRow">
                          <div className="existingPaperTitle">{paper.title || '(无标题)'}</div>
                          <div className="existingPaperMeta">
                            <span>{paper.arxiv_id}</span>
                            {paper.local_pdf_url ? <><span className="dot">·</span><button className="textLink" onClick={(e) => onOpenFileViewer('pdf', `${paper.arxiv_id} PDF`, paper.local_pdf_url!, e)}>查看PDF</button></> : null}
                            {paper.translation_url ? <><span className="dot">·</span><button className="textLink" onClick={(e) => onOpenFileViewer('translation', `${paper.arxiv_id} 翻译文件`, paper.translation_url!, e)}>查看翻译</button></> : null}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
