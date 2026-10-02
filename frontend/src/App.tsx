import { useEffect, useMemo, useState } from 'react'
import { AuthPage } from './components/AuthPage'
import { FileViewerModal } from './components/FileViewerModal'
import { Navbar } from './components/Navbar'
import { ReportPage as ReportPageComponent } from './components/ReportPage'
import { SearchPage as SearchPageComponent } from './components/SearchPage'
import { SelectionSetPage as SelectionSetPageComponent } from './components/SelectionSetPage'
import {
  createWorkflowTaskRequest,
  deleteReportRequest,
  fetchPaperStatusList,
  fetchReportSections,
  fetchSelectionSetPapers,
  fetchSelectionSetReports,
  fetchTask,
  saveSelectionRequest,
  searchArxiv,
  startDownloadTaskRequest,
  startExtractTaskRequest,
  translateSelectionRequest,
  translateSummariesRequest,
} from './api'
import { useAuth } from './hooks/useAuth'
import { useFileViewer } from './hooks/useFileViewer'
import { useSelectionSets } from './hooks/useSelectionSets'
import { useReportEditor } from './hooks/useReportEditor'
import { buildReportPreviewContentFromSections } from './reportUtils'
import type {
  ArxivItem,
  CurrentPage,
  PaperStatus,
  ReportSection,
  SearchHistoryItem,
  SearchOptions,
  SelectionSetResponse,
  TaskInfo,
} from './types'
import './App.css'

function App() {
  const [currentPage, setCurrentPage] = useState<CurrentPage>(() => {
    const savedPage = sessionStorage.getItem('survey2_current_page')
    return savedPage === 'search' || savedPage === 'selection' || savedPage === 'report' ? savedPage : 'search'
  })
  const [query, setQuery] = useState('')
  const [searchOptions, setSearchOptions] = useState<SearchOptions>({ yearFrom: '', yearTo: '', anyKeywords: '' })
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [searchPage, setSearchPage] = useState(1)
  const [searchTotal, setSearchTotal] = useState(0)
  const searchPageSize = 20
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<ArxivItem[]>([])
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [setName, setSetName] = useState('default')
  const [selectResp, setSelectResp] = useState<SelectionSetResponse | null>(null)
  const [translating, setTranslating] = useState(false)
  const [translations, setTranslations] = useState<Record<string, { title_zh: string; abstract_zh: string }>>({})
  const [showChinese, setShowChinese] = useState(false)
  const [translationMessage, setTranslationMessage] = useState<string | null>(null)
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null)
  const [taskMessage, setTaskMessage] = useState<string | null>(null)
  const [paperStatuses, setPaperStatuses] = useState<Record<string, PaperStatus>>({})
  const {
    authToken,
    authUser,
    authMode,
    authUsername,
    authPassword,
    authLoading,
    authError,
    setAuthUsername,
    setAuthPassword,
    changeAuthMode,
    submitAuth,
    logout,
    apiFetch,
  } = useAuth(() => {
    setSelectResp(null)
    setResults([])
    setSearchTotal(0)
    setSearchPage(1)
    setChecked({})
    setPaperStatuses({})
    resetReport()
    setTaskInfo(null)
    setTaskMessage(null)
    setTranslationMessage(null)
    setCurrentPage('search')
    sessionStorage.setItem('survey2_current_page', 'search')
  })


  const searchHistoryStorageKey = useMemo(() => authUser ? `survey_search_history_user_${authUser.id}` : null, [authUser])

  useEffect(() => {
    if (!searchHistoryStorageKey) {
      setSearchHistory([])
      return
    }
    try {
      setSearchHistory(JSON.parse(localStorage.getItem(searchHistoryStorageKey) || '[]') as SearchHistoryItem[])
    } catch {
      setSearchHistory([])
    }
  }, [searchHistoryStorageKey])

  useEffect(() => {
    sessionStorage.setItem('survey2_current_page', currentPage)
  }, [currentPage])


  useEffect(() => {
    if (!error) return
    const timer = window.setTimeout(() => setError(null), 8000)
    return () => window.clearTimeout(timer)
  }, [error])

  const {
    existingSets,
    expandedSetId,
    existingSetDetails,
    existingSetReports,
    selectionFilter,
    selectionSort,
    visibleSelectionSets,
    setExpandedSetId,
    setExistingSetReports,
    setSelectionFilter,
    setSelectionSort,
    fetchExistingSelectionSets,
    toggleExistingSet,
    deleteExistingSet,
    resetSelectionSets,
  } = useSelectionSets({
    apiFetch,
    onError: setError,
    getActiveSelectionSetId: () => selectResp?.selection_set_id ?? null,
    onActiveSelectionSetDeleted: () => {
      setSelectResp(null)
      setResults([])
      setSearchTotal(0)
      setSearchPage(1)
      setChecked({})
      setPaperStatuses({})
    },
  })

  const {
    activeSectionId,
    draftContent,
    reportProgressMessage,
    reportCompletion,
    outlineTemplates,
    outlineRows,
    activeSection,
    setActiveSectionId,
    setDraftContent,
    resetReport,
    loadReport,
    clearDeletedReport,
    createReport,
    applyOutlineTemplate,
    updateSectionTitle,
    saveActiveContent,
    generateActiveSection,
    generateFullReport,
    exportReport,
  } = useReportEditor({
    apiFetch,
    onError: setError,
    refreshSelectionSets: fetchExistingSelectionSets,
    refreshSelectionReports: async (selectionSetId: number) => {
      const reports = await fetchSelectionSetReports(apiFetch, selectionSetId)
      setExistingSetReports((prev) => ({ ...prev, [selectionSetId]: reports }))
    },
  })

  const selectedItems = useMemo(
    () => results.filter((r) => checked[r.arxiv_id]),
    [results, checked],
  )

  const parsedUntranslatedCount = useMemo(
    () => results.filter((item) => paperStatuses[item.arxiv_id]?.parsed && !paperStatuses[item.arxiv_id]?.translated).length,
    [results, paperStatuses],
  )

  const parsedPaperCount = useMemo(
    () => Object.values(paperStatuses).filter((status) => status.parsed).length,
    [paperStatuses],
  )


  const reportTitle = useMemo(() => {
    const keyword = selectResp?.query?.trim() || selectResp?.name?.trim() || ''
    return keyword ? `${keyword}调研报告` : '调研报告'
  }, [selectResp])

  const { viewer, viewerLoading, openFileViewer, closeFileViewer, setViewer } = useFileViewer({
    apiFetch,
    onError: setError,
  })

  async function previewExistingReport(targetReportId: number) {
    try {
      const sectionsResp = await apiFetch(`/api/reports/${targetReportId}/sections`)
      if (!sectionsResp.ok) throw new Error(`加载报告失败：HTTP ${sectionsResp.status}`)
      const loadedSections = (await sectionsResp.json()) as ReportSection[]
      setViewer({ type: 'report', title: `报告预览 #${targetReportId}`, content: buildReportPreviewContentFromSections(loadedSections) })
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  async function loadExistingReport(selectionSetId: number, name: string, count: number, targetReportId: number, selectionQuery?: string | null) {
    try {
      const [papers, loadedSections] = await Promise.all([
        fetchSelectionSetPapers(apiFetch, selectionSetId),
        fetchReportSections(apiFetch, targetReportId),
      ])
      setResults(papers)
      setSearchTotal(papers.length)
      setSearchPage(1)
      setChecked(Object.fromEntries(papers.map((item: ArxivItem) => [item.arxiv_id, true])))
      setSetName(name)
      if (selectionQuery) setQuery(selectionQuery)
      setSelectResp({ selection_set_id: selectionSetId, name, count, query: selectionQuery ?? null })
      loadReport(targetReportId, loadedSections)
      await fetchPaperStatuses(selectionSetId)
      setCurrentPage('report')
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  async function loadSelectionSetToSearch(selectionSetId: number) {
    try {
      const selection = existingSets.find((item) => item.selection_set_id === selectionSetId)
      const papers = await fetchSelectionSetPapers(apiFetch, selectionSetId)
      setResults(papers)
      setSearchTotal(papers.length)
      setSearchPage(1)
      setChecked(Object.fromEntries(papers.map((item: ArxivItem) => [item.arxiv_id, true])))
      setSelectResp(selection ? { selection_set_id: selectionSetId, name: selection.name, count: selection.count, query: selection.query ?? null } : { selection_set_id: selectionSetId, name: '参考文献选择集', count: papers.length, query: null })
      setSetName(selection?.name ?? 'default')
      if (selection?.query) setQuery(selection.query)
      resetReport()
      setPaperStatuses({})
      await fetchPaperStatuses(selectionSetId)
      setCurrentPage('search')
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  async function deleteExistingReport(selectionSetId: number, targetReportId: number) {
    const confirmed = window.confirm(`确定删除报告 #${targetReportId} 吗？删除后无法恢复。`)
    if (!confirmed) return
    try {
      await deleteReportRequest(apiFetch, targetReportId)
      setExistingSetReports((prev) => ({
        ...prev,
        [selectionSetId]: (prev[selectionSetId] ?? []).filter((report) => report.report_id !== targetReportId),
      }))
      clearDeletedReport(targetReportId)
      if (viewer?.title.includes(`#${targetReportId}`)) setViewer(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    }
  }

  function updateSearchOption(key: keyof SearchOptions, value: string) {
    setSearchOptions((prev) => ({ ...prev, [key]: value }))
  }

  function saveSearchHistory(nextQuery: string, options: SearchOptions) {
    const item: SearchHistoryItem = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      query: nextQuery,
      searchedAt: new Date().toLocaleString(),
      ...options,
    }
    setSearchHistory((prev) => {
      const deduped = prev.filter((entry) => entry.query !== item.query)
      const next = [item, ...deduped].slice(0, 10)
      if (searchHistoryStorageKey) localStorage.setItem(searchHistoryStorageKey, JSON.stringify(next))
      return next
    })
  }

  function applySearchHistory(item: SearchHistoryItem) {
    setQuery(item.query)
    setSearchOptions({
      yearFrom: item.yearFrom,
      yearTo: item.yearTo,
      anyKeywords: item.anyKeywords,
    })
  }

  function clearSearchHistory() {
    if (searchHistoryStorageKey) localStorage.removeItem(searchHistoryStorageKey)
    setSearchHistory([])
  }

  async function doSearch(targetPage = 1) {
    setLoading(true)
    setSearching(true)
    setError(null)
    setTranslationMessage(null)
    setTaskInfo(null)
    setTaskMessage(null)
    setSelectResp(null)
    setPaperStatuses({})
    try {
      const data = await searchArxiv(apiFetch, query, searchOptions, targetPage, searchPageSize)
      setResults(data.items)
      setSearchTotal(data.total)
      setSearchPage(targetPage)
      saveSearchHistory(query.trim(), searchOptions)
      setChecked({})
      await fetchExistingSelectionSets()
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
      setSearching(false)
    }
  }

  function changeSearchPage(nextPage: number) {
    if (loading || !query.trim()) return
    void doSearch(nextPage)
  }

  async function saveSelection() {
    setLoading(true)
    setError(null)
    setTranslationMessage(null)
    setTaskInfo(null)
    setTaskMessage(null)
    setSelectResp(null)
    resetReport()
    setPaperStatuses({})
    try {
      const data = await saveSelectionRequest(apiFetch, setName || 'default', query.trim(), selectedItems)
      setSelectResp(data)
      await fetchPaperStatuses(data.selection_set_id)
      await fetchExistingSelectionSets()
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  async function fetchPaperStatuses(selectionSetId: number) {
    try {
      const data = await fetchPaperStatusList(apiFetch, selectionSetId)
      const mapped: Record<string, PaperStatus> = {}
      for (const item of data) mapped[item.arxiv_id] = item
      setPaperStatuses(mapped)
    } catch {
      // ignore
    }
  }

  async function translateSelection() {
    if (!selectResp) return
    setTranslating(true)
    setError(null)
    setTranslationMessage(null)
    try {
      const data = await translateSelectionRequest(apiFetch, selectResp.selection_set_id)
      setTranslations((prev) => ({ ...prev, ...(data.translations ?? {}) }))
      setShowChinese(true)
      const skippedCount = data.skipped?.length ?? 0
      const alreadyCount = data.already_translated?.length ?? 0
      setTranslationMessage(
        skippedCount > 0 || alreadyCount > 0
          ? `已新增完成 ${data.translated} 篇全文翻译，跳过 ${alreadyCount} 篇已有翻译，另有 ${skippedCount} 篇因未解析正文被跳过；结果已保存到服务器存储目录`
          : `已完成 ${data.translated} 篇参考文献全文翻译，并保存到服务器存储目录`
      )
      await fetchPaperStatuses(selectResp.selection_set_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setTranslating(false)
    }
  }

  async function toggleChineseSummaries() {
    if (showChinese) {
      setShowChinese(false)
      return
    }
    const targetItems = selectedItems.length > 0 ? selectedItems : results
    const missingItems = targetItems.filter(
      (item) => !(translations[item.arxiv_id]?.title_zh || item.title_zh || translations[item.arxiv_id]?.abstract_zh || item.abstract_zh),
    )
    if (missingItems.length === 0) {
      setShowChinese(true)
      return
    }
    setTranslating(true)
    setError(null)
    setTranslationMessage(`正在翻译 ${missingItems.length} 篇论文的标题和摘要...`)
    try {
      const data = await translateSummariesRequest(apiFetch, missingItems)
      setTranslations((prev) => ({ ...prev, ...(data.translations ?? {}) }))
      setShowChinese(true)
      setTranslationMessage(`已完成 ${data.translated} 篇论文的中文标题和摘要翻译。`)
    } catch (e) {
      setTranslationMessage(null)
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setTranslating(false)
    }
  }

  async function pollTaskUntilDone(taskId: number): Promise<TaskInfo> {
    return new Promise((resolve, reject) => {
      const timer = window.setInterval(async () => {
        try {
          const data = await fetchTask(apiFetch, taskId)
          if (!data) return
          setTaskInfo(data)
          if (data.message) setTaskMessage(data.message)
          if (data.status === 'completed') {
            window.clearInterval(timer)
            resolve(data)
          }
          if (data.status === 'failed') {
            window.clearInterval(timer)
            reject(new Error(data.message || '任务失败'))
          }
        } catch (e) {
          window.clearInterval(timer)
          reject(e)
        }
      }, 1500)
    })
  }

  async function createWorkflowTask() {
    if (!selectResp) return
    setLoading(true)
    setError(null)
    setTaskMessage(null)
    try {
      const data = await createWorkflowTaskRequest(apiFetch, selectResp.selection_set_id)
      setTaskInfo(data)
      setTaskMessage('任务已创建，可以开始下载 PDF。')
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  async function runDownloadTask() {
    if (!taskInfo) return
    setLoading(true)
    setError(null)
    try {
      const data = await startDownloadTaskRequest(apiFetch, taskInfo.task_id)
      setTaskInfo(data)
      setTaskMessage('开始下载 PDF...')
      await pollTaskUntilDone(taskInfo.task_id)
      if (selectResp) await fetchPaperStatuses(selectResp.selection_set_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  async function runExtractTask() {
    if (!taskInfo) return
    setLoading(true)
    setError(null)
    try {
      const data = await startExtractTaskRequest(apiFetch, taskInfo.task_id)
      setTaskInfo(data)
      setTaskMessage('开始解析正文...')
      await pollTaskUntilDone(taskInfo.task_id)
      if (selectResp) await fetchPaperStatuses(selectResp.selection_set_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }

  async function exitSelectionSet(confirmUnsaved = true) {
    if (confirmUnsaved && activeSection && draftContent !== (activeSection.content_md ?? '')) {
      const confirmed = window.confirm('当前章节有未保存的修改，确定退出该选择集吗？')
      if (!confirmed) return
    }
    const currentSelectionSetId = selectResp?.selection_set_id
    setSelectResp(null)
    setResults([])
    setSearchTotal(0)
    setSearchPage(1)
    setChecked({})
    setPaperStatuses({})
    resetReport()
    setTaskInfo(null)
    setTaskMessage(null)
    setTranslationMessage(null)
    setExpandedSetId(null)
    setCurrentPage('search')
    await fetchExistingSelectionSets()
    if (currentSelectionSetId) {
      const reports = await fetchSelectionSetReports(apiFetch, currentSelectionSetId)
      setExistingSetReports((prev) => ({ ...prev, [currentSelectionSetId]: reports }))
    }
  }

  useEffect(() => {
    if (authToken) void fetchExistingSelectionSets()
  }, [authToken, fetchExistingSelectionSets])

  useEffect(() => {
    if (!authToken) resetSelectionSets()
  }, [authToken, resetSelectionSets])

  if (!authUser || !authToken) {
    return (
      <AuthPage
        authMode={authMode}
        authUsername={authUsername}
        authPassword={authPassword}
        authLoading={authLoading}
        authError={authError}
        onAuthModeChange={changeAuthMode}
        onUsernameChange={setAuthUsername}
        onPasswordChange={setAuthPassword}
        onSubmit={submitAuth}
      />
    )
  }

  // ── 选择集页 JSX ──
  const SelectionPage = (
    <SelectionSetPageComponent
      error={error}
      existingSets={existingSets}
      visibleSelectionSets={visibleSelectionSets}
      selectionFilter={selectionFilter}
      selectionSort={selectionSort}
      expandedSetId={expandedSetId}
      existingSetDetails={existingSetDetails}
      existingSetReports={existingSetReports}
      onRefresh={fetchExistingSelectionSets}
      onBackToSearch={() => setCurrentPage('search')}
      onSelectionFilterChange={setSelectionFilter}
      onSelectionSortChange={setSelectionSort}
      onToggleSet={toggleExistingSet}
      onDeleteSet={deleteExistingSet}
      onLoadSelectionSetToSearch={loadSelectionSetToSearch}
      onPreviewReport={previewExistingReport}
      onLoadReport={loadExistingReport}
      onDeleteReport={deleteExistingReport}
      onOpenFileViewer={openFileViewer}
    />
  )

  const SearchPage = (
    <SearchPageComponent
      query={query}
      loading={loading}
      error={error}
      results={results}
      checked={checked}
      setName={setName}
      selectResp={selectResp}
      existingSets={existingSets}
      taskInfo={taskInfo}
      taskMessage={taskMessage}
      translationMessage={translationMessage}
      translations={translations}
      showChinese={showChinese}
      translating={translating}
      parsedUntranslatedCount={parsedUntranslatedCount}
      paperStatuses={paperStatuses}
      selectedItems={selectedItems}
      searching={searching}
      searchPage={searchPage}
      searchPageSize={searchPageSize}
      searchTotal={searchTotal}
      searchOptions={searchOptions}
      searchHistory={searchHistory}
      onQueryChange={setQuery}
      onSearchOptionChange={updateSearchOption}
      onApplySearchHistory={applySearchHistory}
      onClearSearchHistory={clearSearchHistory}
      onSearch={() => doSearch(1)}
      onSearchPageChange={changeSearchPage}
      onSetNameChange={setSetName}
      onToggleAll={() => setChecked(Object.fromEntries(results.map((item: ArxivItem) => [item.arxiv_id, true])))}
      onClearSelection={() => setChecked({})}
      onToggleChinese={toggleChineseSummaries}
      onSaveSelection={saveSelection}
      onCreateTask={createWorkflowTask}
      onDownloadTask={runDownloadTask}
      onExtractTask={runExtractTask}
      onTranslateSelection={translateSelection}
      onCheckedChange={(arxivId: string, value: boolean) => setChecked((prev) => ({ ...prev, [arxivId]: value }))}
      onOpenFileViewer={openFileViewer}
      onLoadExistingSelectionSet={loadSelectionSetToSearch}
      onExitSelectionSet={() => exitSelectionSet(false)}
    />
  )

  // ── 报告页 JSX ──
  const ReportPage = (
    <ReportPageComponent
      loading={loading}
      error={error}
      reportProgressMessage={reportProgressMessage}
      selectResp={selectResp}
      reportCompletion={reportCompletion}
      parsedPaperCount={parsedPaperCount}
      outlineTemplates={outlineTemplates}
      reportTitle={reportTitle}
      outlineRows={outlineRows}
      activeSection={activeSection}
      activeSectionId={activeSectionId}
      draftContent={draftContent}
      onCreateReport={() => createReport(selectResp, parsedPaperCount, setLoading)}
      onApplyOutlineTemplate={(template) => applyOutlineTemplate(template, setLoading)}
      onGenerateFullReport={() => generateFullReport(selectResp, setLoading)}
      onExitSelectionSet={() => exitSelectionSet()}
      onExportReport={(format) => exportReport(format, setLoading)}
      onSetCurrentPage={setCurrentPage}
      onSelectSection={(sectionId, content) => { setActiveSectionId(sectionId); setDraftContent(content) }}
      onGenerateSection={() => generateActiveSection(setLoading)}
      onSaveContent={() => saveActiveContent(setLoading)}
      onUpdateDraftContent={setDraftContent}
      onUpdateSectionTitle={updateSectionTitle}
    />
  )

  return (
    <div className="app">
      <Navbar
        currentPage={currentPage}
        authUser={authUser}
        selectResp={selectResp}
        onPageChange={setCurrentPage}
        onLogout={logout}
      />
      {currentPage === 'search' ? SearchPage : currentPage === 'selection' ? SelectionPage : ReportPage}
      <FileViewerModal viewer={viewer} viewerLoading={viewerLoading} onClose={closeFileViewer} />
    </div>
  )
}

export default App
