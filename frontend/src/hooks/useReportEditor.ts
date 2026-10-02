import { useCallback, useMemo, useState } from 'react'
import {
  applyOutlineTemplateRequest,
  createReportRequest,
  exportReportRequest,
  fetchOutlineTemplatesRequest,
  fetchReportSections,
  generateFullReportRequest,
  generateSectionRequest,
  saveSectionContentRequest,
  updateSectionTitleRequest,
} from '../api'
import { buildOutlineRows, calculateReportCompletion } from '../reportUtils'
import type { ReportOutlineTemplate, ReportSection, SelectionSetResponse } from '../types'

type UseReportEditorOptions = {
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
  onError: (message: string | null) => void
  refreshSelectionSets: () => Promise<void>
  refreshSelectionReports: (selectionSetId: number) => Promise<void>
}

export function useReportEditor({ apiFetch, onError, refreshSelectionSets, refreshSelectionReports }: UseReportEditorOptions) {
  const [reportId, setReportId] = useState<number | null>(null)
  const [sections, setSections] = useState<ReportSection[]>([])
  const [activeSectionId, setActiveSectionId] = useState<number | null>(null)
  const [draftContent, setDraftContent] = useState('')
  const [reportProgressMessage, setReportProgressMessage] = useState<string | null>(null)
  const [outlineTemplates, setOutlineTemplates] = useState<ReportOutlineTemplate[]>([])

  const reportCompletion = useMemo(() => calculateReportCompletion(sections), [sections])
  const outlineRows = useMemo(() => buildOutlineRows(sections), [sections])
  const activeSection = useMemo(
    () => sections.find((s) => s.id === activeSectionId) ?? null,
    [sections, activeSectionId],
  )

  const resetReport = useCallback(() => {
    setReportId(null)
    setSections([])
    setActiveSectionId(null)
    setDraftContent('')
    setReportProgressMessage(null)
    setOutlineTemplates([])
  }, [])

  const loadReport = useCallback((targetReportId: number, loadedSections: ReportSection[]) => {
    setReportId(targetReportId)
    setSections(loadedSections)
    const firstSection = loadedSections[0]
    setActiveSectionId(firstSection?.id ?? null)
    setDraftContent(firstSection?.content_md ?? '')
    setReportProgressMessage('已加载报告')
    setOutlineTemplates([])
  }, [])

  const clearDeletedReport = useCallback((targetReportId: number) => {
    setReportId((current) => {
      if (current !== targetReportId) return current
      setSections([])
      setActiveSectionId(null)
      setDraftContent('')
      setReportProgressMessage('当前报告已删除。')
      return null
    })
  }, [])

  const createReport = useCallback(async (selectResp: SelectionSetResponse | null, parsedPaperCount: number, setLoading: (value: boolean) => void) => {
    if (!selectResp || parsedPaperCount === 0) return
    setLoading(true)
    onError(null)
    setReportProgressMessage('正在创建报告...')
    try {
      const data = await createReportRequest(apiFetch, selectResp.selection_set_id)
      setReportId(data.report_id)
      setSections([])
      setActiveSectionId(null)
      setDraftContent('')
      setReportProgressMessage('报告已创建，正在调用大模型推荐目录模板...')
      const templates = await fetchOutlineTemplatesRequest(apiFetch, data.report_id)
      setOutlineTemplates(templates)
      setReportProgressMessage(templates.length > 0 ? '请选择一种目录模板。' : '未获取到目录模板，请稍后重试。')
      await refreshSelectionSets()
      await refreshSelectionReports(selectResp.selection_set_id)
    } catch (e) {
      setReportProgressMessage(null)
      onError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }, [apiFetch, onError, refreshSelectionReports, refreshSelectionSets])

  const applyOutlineTemplate = useCallback(async (template: ReportOutlineTemplate, setLoading: (value: boolean) => void) => {
    if (!reportId) return
    setLoading(true)
    onError(null)
    setReportProgressMessage(`正在应用「${template.name}」...`)
    try {
      const data = await applyOutlineTemplateRequest(apiFetch, reportId, template.outline)
      setSections(data)
      const firstSection = data[0]
      setActiveSectionId(firstSection?.id ?? null)
      setDraftContent(firstSection?.content_md ?? '')
      setOutlineTemplates([])
      setReportProgressMessage(`已应用「${template.name}」，可以开始自动生成整篇报告。`)
    } catch (e) {
      onError(e instanceof Error ? e.message : '未知错误')
      setReportProgressMessage(null)
    } finally {
      setLoading(false)
    }
  }, [apiFetch, onError, reportId])

  const updateSectionTitle = useCallback(async (sectionId: number, title: string) => {
    if (!reportId) return
    try {
      await updateSectionTitleRequest(apiFetch, reportId, sectionId, title)
    } catch {
      // ignore
    }
  }, [apiFetch, reportId])

  const saveActiveContent = useCallback(async (setLoading: (value: boolean) => void) => {
    if (!reportId || !activeSectionId) return
    setLoading(true)
    onError(null)
    try {
      await saveSectionContentRequest(apiFetch, reportId, activeSectionId, draftContent)
      setSections((prev) => prev.map((s) => (s.id === activeSectionId ? { ...s, content_md: draftContent } : s)))
    } catch (e) {
      onError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }, [activeSectionId, apiFetch, draftContent, onError, reportId])

  const generateActiveSection = useCallback(async (setLoading: (value: boolean) => void) => {
    if (!reportId || !activeSectionId) return
    setLoading(true)
    onError(null)
    try {
      const data = await generateSectionRequest(apiFetch, reportId, activeSectionId)
      setDraftContent(data.content_md ?? '')
      setSections((prev) => prev.map((s) => (s.id === activeSectionId ? { ...s, content_md: data.content_md ?? '' } : s)))
    } catch (e) {
      onError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }, [activeSectionId, apiFetch, onError, reportId])

  const generateFullReport = useCallback(async (selectResp: SelectionSetResponse | null, setLoading: (value: boolean) => void) => {
    if (!reportId) return
    setLoading(true)
    onError(null)
    setReportProgressMessage('正在调用大模型生成整篇报告')
    try {
      const resp = await generateFullReportRequest(apiFetch, reportId)
      setReportProgressMessage('模型生成完成，正在刷新章节内容...')
      const data = await fetchReportSections(apiFetch, reportId)
      setSections(data)
      if (data.length > 0) {
        const nextActive = activeSectionId ?? data[0].id
        const nextSection = data.find((item) => item.id === nextActive) ?? data[0]
        setActiveSectionId(nextSection.id)
        setDraftContent(nextSection.content_md ?? '')
      }
      setReportProgressMessage(`整篇报告生成完成（${resp.count ?? data.length} 个章节）`)
      if (selectResp) await refreshSelectionReports(selectResp.selection_set_id)
    } catch (e) {
      setReportProgressMessage(null)
      onError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }, [activeSectionId, apiFetch, onError, refreshSelectionReports, reportId])

  const exportReport = useCallback(async (format: 'md' | 'docx' | 'pdf', setLoading: (value: boolean) => void) => {
    if (!reportId) return
    setLoading(true)
    onError(null)
    try {
      await exportReportRequest(apiFetch, reportId, format)
      window.open(`/api/reports/${reportId}/export/download?format=${format}`, '_blank')
    } catch (e) {
      onError(e instanceof Error ? e.message : '未知错误')
    } finally {
      setLoading(false)
    }
  }, [apiFetch, onError, reportId])

  return {
    reportId,
    sections,
    activeSectionId,
    draftContent,
    reportProgressMessage,
    reportCompletion,
    outlineTemplates,
    outlineRows,
    activeSection,
    setReportId,
    setSections,
    setActiveSectionId,
    setDraftContent,
    setReportProgressMessage,
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
  }
}
