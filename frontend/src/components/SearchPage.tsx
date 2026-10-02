import { useState } from 'react'
import type { MouseEvent } from 'react'
import type { ArxivItem, ExistingSelectionSet, PaperStatus, SearchHistoryItem, SearchOptions, SelectionSetResponse, TaskInfo } from '../types'

type SearchPageProps = {
  query: string
  loading: boolean
  searching: boolean
  error: string | null
  results: ArxivItem[]
  checked: Record<string, boolean>
  setName: string
  selectResp: SelectionSetResponse | null
  existingSets: ExistingSelectionSet[]
  taskInfo: TaskInfo | null
  taskMessage: string | null
  translationMessage: string | null
  translations: Record<string, { title_zh: string; abstract_zh: string }>
  showChinese: boolean
  translating: boolean
  parsedUntranslatedCount: number
  paperStatuses: Record<string, PaperStatus>
  selectedItems: ArxivItem[]
  searchPage: number
  searchPageSize: number
  searchTotal: number
  searchOptions: SearchOptions
  searchHistory: SearchHistoryItem[]
  onQueryChange: (value: string) => void
  onSearchOptionChange: (key: keyof SearchOptions, value: string) => void
  onApplySearchHistory: (item: SearchHistoryItem) => void
  onClearSearchHistory: () => void
  onSearch: () => void
  onSearchPageChange: (page: number) => void
  onSetNameChange: (value: string) => void
  onToggleAll: () => void
  onClearSelection: () => void
  onToggleChinese: () => void
  onSaveSelection: () => void
  onCreateTask: () => void
  onDownloadTask: () => void
  onExtractTask: () => void
  onTranslateSelection: () => void
  onCheckedChange: (arxivId: string, checked: boolean) => void
  onOpenFileViewer: (type: 'pdf' | 'translation', title: string, url: string, event?: MouseEvent) => void
  onLoadExistingSelectionSet: (selectionSetId: number) => void
  onExitSelectionSet: () => void
}

export function SearchPage({
  query,
  loading,
  searching,
  error,
  results,
  checked,
  setName,
  selectResp,
  existingSets,
  taskInfo,
  taskMessage,
  translationMessage,
  translations,
  showChinese,
  translating,
  parsedUntranslatedCount,
  paperStatuses,
  selectedItems,
  searchPage,
  searchPageSize,
  searchTotal,
  searchOptions,
  searchHistory,
  onQueryChange,
  onSearchOptionChange,
  onApplySearchHistory,
  onClearSearchHistory,
  onSearch,
  onSearchPageChange,
  onSetNameChange,
  onToggleAll,
  onClearSelection,
  onToggleChinese,
  onSaveSelection,
  onCreateTask,
  onDownloadTask,
  onExtractTask,
  onTranslateSelection,
  onCheckedChange,
  onOpenFileViewer,
  onLoadExistingSelectionSet,
  onExitSelectionSet,
}: SearchPageProps) {
  const [draftExistingSetId, setDraftExistingSetId] = useState('')
  const activeExistingSetId = selectResp ? String(selectResp.selection_set_id) : ''
  const selectedExistingSetId = draftExistingSetId || activeExistingSetId
  const totalPages = Math.max(1, Math.ceil(searchTotal / searchPageSize))
  const pageNumbers = Array.from({ length: Math.min(5, totalPages) }, (_, index) => {
    const start = Math.min(Math.max(searchPage - 2, 1), Math.max(totalPages - 4, 1))
    return start + index
  })

  const loadSelectedExistingSet = () => {
    if (!selectedExistingSetId) return
    onLoadExistingSelectionSet(Number(selectedExistingSetId))
    setDraftExistingSetId('')
  }

  const exitCurrentSelectionSet = () => {
    setDraftExistingSetId('')
    onExitSelectionSet()
  }

  return (
    <div className="page">
      <div className="searchBar">
        <input
          className="input searchInput"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          placeholder="输入论文检索关键词"
        />
        <button className="btn primary" onClick={onSearch} disabled={loading || !query.trim()}>
          {searching ? '检索中...' : '检索'}
        </button>
      </div>
      <div className="advancedSearchPanel">
        <div className="advancedSearchHeader">
          <div>
            <div className="advancedSearchTitle">年份筛选</div>
            <div className="advancedSearchHint">只按年份范围过滤论文，更轻量直观。</div>
          </div>
        </div>
        <div className="advancedSearchGrid yearOnlyGrid">
          <label className="advancedField">
            <span>起始年份</span>
            <input className="input" value={searchOptions.yearFrom} onChange={(e) => onSearchOptionChange('yearFrom', e.target.value)} placeholder="如 2020" />
          </label>
          <label className="advancedField">
            <span>结束年份</span>
            <input className="input" value={searchOptions.yearTo} onChange={(e) => onSearchOptionChange('yearTo', e.target.value)} placeholder="如 2026" />
          </label>
        </div>
        <div className="searchHistoryBar">
          <div className="searchHistoryHead">
            <span>最近检索</span>
            <button className="textLink" onClick={onClearSearchHistory}>清空历史</button>
          </div>
          {searchHistory.length === 0 ? (
            <div className="muted compactMuted">暂无历史记录。</div>
          ) : (
            <div className="searchHistoryList">
              {searchHistory.map((item) => (
                <button key={item.id} className="historyChip" onClick={() => onApplySearchHistory(item)} title={item.searchedAt}>
                  <span className="historyChipQuery">{item.query}</span>
                  <span className="historyChipMeta">{item.searchedAt}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      {existingSets.length > 0 && (
        <div className="selectionLoaderBar">
          <div className="selectionLoaderInfo">
            <div className="selectionLoaderLabel">参考文献选择集</div>
            <div className="selectionLoaderHint">
              {selectResp ? `当前：${selectResp.name}（${selectResp.count} 篇）` : '可加载已保存的选择集到论文检索'}
            </div>
          </div>
          <div className="selectionLoaderActions">
            <select className="input selectionLoaderSelect" value={selectedExistingSetId} onChange={(e) => setDraftExistingSetId(e.target.value)}>
              <option value="">选择已有参考文献选择集</option>
              {existingSets.map((item) => (
                <option key={item.selection_set_id} value={item.selection_set_id}>
                  {item.name}（{item.query || '未记录关键词'}，{item.count} 篇）
                </option>
              ))}
            </select>
            <button className="btn primary" onClick={loadSelectedExistingSet} disabled={loading || !selectedExistingSetId}>
              加载到检索
            </button>
            {selectResp && (
              <button className="btn danger subtleDanger" onClick={exitCurrentSelectionSet} disabled={loading}>退出选择集</button>
            )}
          </div>
        </div>
      )}
      <div className="panel">
        <div className="panelHead">
          <h2 className="resultTitle">
            检索结果
            <span className="countBadge selectedCountBadge">已选 {selectedItems.length}</span>
            <span className="countBadge totalCountBadge">本页 {results.length}</span>
            <span className="countBadge totalCountBadge">总计 {searchTotal}</span>
          </h2>
          <div className="right">
            <input className="input small" value={setName} onChange={(e) => onSetNameChange(e.target.value)} placeholder="参考文献选择集名称" />
            <button className="btn" onClick={onToggleAll} disabled={results.length === 0}>全选</button>
            <button className="btn" onClick={onClearSelection} disabled={selectedItems.length === 0}>清空选择</button>
            <button className="btn" onClick={onToggleChinese} disabled={translating || results.length === 0}>
              {translating ? '翻译中...' : showChinese ? '显示英文摘要' : '显示中文摘要'}
            </button>
            <button className="btn primary" onClick={onSaveSelection} disabled={loading || selectedItems.length === 0}>
              保存选择（{selectedItems.length}）
            </button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        <div className="muted" style={{ padding: '10px 14px 0' }}>
          全文翻译基于已解析的正文 text 文件；请先完成论文下载与文本解析，再执行全文翻译。
        </div>
        {selectResp && (
          <div className="workflowBar">
            <button className="btn" onClick={onCreateTask} disabled={loading || !selectResp}>
              {taskInfo ? '重新创建任务' : '1. 创建任务'}
            </button>
            <button className="btn" onClick={onDownloadTask} disabled={loading || !taskInfo}>2. 下载 PDF</button>
            <button className="btn" onClick={onExtractTask} disabled={loading || !taskInfo}>3. 解析正文</button>
            <button className="btn primary" onClick={onTranslateSelection} disabled={translating || !selectResp || parsedUntranslatedCount === 0} title={parsedUntranslatedCount === 0 ? '没有已解析且未翻译的论文，请先完成解析或选择未翻译论文。' : undefined}>
              {translating ? '全文翻译中...' : `4. 全文翻译${parsedUntranslatedCount > 0 ? `（${parsedUntranslatedCount}）` : ''}`}
            </button>
          </div>
        )}
        {taskInfo && (
          <div className="taskCard">
            <div className="taskRow">
              <span>任务 ID：{taskInfo.task_id}</span>
              <span>状态：{taskInfo.status}</span>
              <span>步骤：{taskInfo.step}</span>
              <span>进度：{taskInfo.progress}%</span>
            </div>
            {taskMessage ? <div className="taskMessage">{taskMessage}</div> : null}
            <div className="taskHint">请按顺序执行：创建任务 → 下载 PDF → 解析正文；完成解析后可进入报告生成。</div>
          </div>
        )}
        {translationMessage && <div className="ok">{translationMessage}</div>}
        {searchTotal > 0 && (
          <div className="paginationBar">
            <button className="btn" onClick={() => onSearchPageChange(searchPage - 1)} disabled={loading || searchPage <= 1}>上一页</button>
            <div className="pageNumberGroup">
              {pageNumbers.map((page) => (
                <button key={page} className={`pageNumberButton ${page === searchPage ? 'active' : ''}`} onClick={() => onSearchPageChange(page)} disabled={loading || page === searchPage}>
                  {page}
                </button>
              ))}
            </div>
            <span className="paginationInfo">第 {searchPage} / {totalPages} 页，每页 {searchPageSize} 条，共 {searchTotal} 条</span>
            <button className="btn" onClick={() => onSearchPageChange(searchPage + 1)} disabled={loading || searchPage >= totalPages}>下一页</button>
          </div>
        )}
        <div className="list">
          {results.length === 0 ? (
            <div className="empty">暂无数据。输入关键词后点击"检索"。</div>
          ) : (
            results.map((r) => (
              <label key={r.arxiv_id} className="item">
                <input type="checkbox" checked={!!checked[r.arxiv_id]} onChange={(e) => onCheckedChange(r.arxiv_id, e.target.checked)} />
                <div className="meta">
                  <div className="row1">
                    <div className="paperTitle">{showChinese && (translations[r.arxiv_id]?.title_zh || r.title_zh) ? (translations[r.arxiv_id]?.title_zh || r.title_zh) : r.title || '(无标题)'}</div>
                    <div className="paperMetaRight">
                      <div className="paperStatusGroup">
                        {paperStatuses[r.arxiv_id]?.downloaded ? <span className="statusBadge downloaded">已下载</span> : null}
                        {paperStatuses[r.arxiv_id]?.parsed ? <span className="statusBadge parsed">已解析</span> : null}
                        {paperStatuses[r.arxiv_id]?.translated ? <span className="statusBadge translated">已翻译</span> : null}
                      </div>
                      <div className="paperId">{r.arxiv_id}</div>
                    </div>
                  </div>
                  <div className="row2">{r.authors?.slice(0, 6).join(', ')}</div>
                  <div className="row3">{showChinese && (translations[r.arxiv_id]?.abstract_zh || r.abstract_zh) ? (translations[r.arxiv_id]?.abstract_zh || r.abstract_zh) : r.abstract}</div>
                  <div className="row4">
                    <a href={r.pdf_url} target="_blank" rel="noreferrer">arXiv PDF</a>
                    {paperStatuses[r.arxiv_id]?.local_pdf_url || r.local_pdf_url ? <><span className="dot">·</span><button className="textLink" onClick={(e) => onOpenFileViewer('pdf', `${r.arxiv_id} PDF`, (paperStatuses[r.arxiv_id]?.local_pdf_url ?? r.local_pdf_url)!, e)}>网页内查看PDF</button></> : null}
                    {paperStatuses[r.arxiv_id]?.translation_url || r.translation_url ? <><span className="dot">·</span><button className="textLink" onClick={(e) => onOpenFileViewer('translation', `${r.arxiv_id} 翻译文件`, (paperStatuses[r.arxiv_id]?.translation_url ?? r.translation_url)!, e)}>网页内查看翻译</button></> : null}
                    <span className="dot">·</span><span className="time">published: {r.published ?? '-'}</span>
                    <span className="dot">·</span><span className="time">updated: {r.updated ?? '-'}</span>
                  </div>
                </div>
              </label>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
