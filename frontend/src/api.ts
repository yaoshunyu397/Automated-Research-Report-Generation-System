import type {
  ArxivItem,
  ArxivSearchResponse,
  AuthResponse,
  ExistingReport,
  ExistingSelectionSet,
  PaperStatus,
  ReportCreateResponse,
  ReportOutlineNode,
  ReportOutlineTemplate,
  ReportSection,
  SearchOptions,
  SelectionSetResponse,
  TaskInfo,
} from './types'

export type ApiFetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type SummaryTranslationResponse = {
  translated: number
  translations?: Record<string, { title_zh: string; abstract_zh: string }>
}

export type FullTranslationResponse = SummaryTranslationResponse & {
  saved_files?: string[]
  skipped?: string[]
  already_translated?: string[]
}

async function readErrorDetail(response: Response, fallbackPrefix: string) {
  let detail = `HTTP ${response.status}`
  try {
    const err = (await response.json()) as { detail?: string }
    if (err.detail) detail = err.detail
  } catch {
    // ignore non-json error response
  }
  return `${fallbackPrefix}：${detail}`
}

async function ensureOk(response: Response, message: string) {
  if (!response.ok) throw new Error(`${message}：HTTP ${response.status}`)
}

export async function submitAuthRequest(mode: 'login' | 'register', username: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`/api/auth/${mode}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error(await readErrorDetail(response, '认证失败'))
  return (await response.json()) as AuthResponse
}

export async function searchArxiv(apiFetch: ApiFetch, query: string, options?: SearchOptions, page = 1, pageSize = 20): Promise<ArxivSearchResponse> {
  const start = Math.max(page - 1, 0) * pageSize
  const params = new URLSearchParams({ q: query, max_results: String(pageSize), start: String(start), sort_by: 'submittedDate' })
  if (options?.yearFrom.trim()) params.set('year_from', options.yearFrom.trim())
  if (options?.yearTo.trim()) params.set('year_to', options.yearTo.trim())
  if (options?.anyKeywords.trim()) params.set('any_keywords', options.anyKeywords.trim())
  const response = await apiFetch(`/api/arxiv/search?${params.toString()}`)
  if (!response.ok) throw new Error(await readErrorDetail(response, '检索失败'))
  return (await response.json()) as ArxivSearchResponse
}

export async function fetchSelectionSets(apiFetch: ApiFetch): Promise<ExistingSelectionSet[]> {
  const response = await apiFetch('/api/papers/selection_sets')
  if (!response.ok) return []
  return (await response.json()) as ExistingSelectionSet[]
}

export async function fetchSelectionSetPapers(apiFetch: ApiFetch, selectionSetId: number): Promise<ArxivItem[]> {
  const response = await apiFetch(`/api/papers/selection_set/${selectionSetId}`)
  await ensureOk(response, '加载选择集失败')
  return (await response.json()) as ArxivItem[]
}

export async function fetchSelectionSetReports(apiFetch: ApiFetch, selectionSetId: number): Promise<ExistingReport[]> {
  const response = await apiFetch(`/api/reports/selection_set/${selectionSetId}`)
  if (!response.ok) return []
  return (await response.json()) as ExistingReport[]
}

export async function fetchReportSections(apiFetch: ApiFetch, reportId: number): Promise<ReportSection[]> {
  const response = await apiFetch(`/api/reports/${reportId}/sections`)
  await ensureOk(response, '加载报告失败')
  return (await response.json()) as ReportSection[]
}

export async function fetchPaperStatusList(apiFetch: ApiFetch, selectionSetId: number): Promise<PaperStatus[]> {
  const response = await apiFetch(`/api/papers/selection_set/${selectionSetId}/statuses`)
  if (!response.ok) return []
  return (await response.json()) as PaperStatus[]
}

export async function saveSelectionRequest(apiFetch: ApiFetch, name: string, query: string, items: ArxivItem[]): Promise<SelectionSetResponse> {
  const response = await apiFetch('/api/papers/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, query, items }),
  })
  await ensureOk(response, '保存失败')
  return (await response.json()) as SelectionSetResponse
}

export async function deleteSelectionSetRequest(apiFetch: ApiFetch, selectionSetId: number) {
  const response = await apiFetch(`/api/papers/selection_set/${selectionSetId}`, { method: 'DELETE' })
  await ensureOk(response, '删除选择集失败')
}

export async function deleteReportRequest(apiFetch: ApiFetch, reportId: number) {
  const response = await apiFetch(`/api/reports/${reportId}`, { method: 'DELETE' })
  await ensureOk(response, '删除报告失败')
}

export async function translateSelectionRequest(apiFetch: ApiFetch, selectionSetId: number): Promise<FullTranslationResponse> {
  const response = await apiFetch(`/api/translate/selection_set/${selectionSetId}`, { method: 'POST' })
  await ensureOk(response, '翻译失败')
  return (await response.json()) as FullTranslationResponse
}

export async function translateSummariesRequest(apiFetch: ApiFetch, items: ArxivItem[]): Promise<SummaryTranslationResponse> {
  const response = await apiFetch('/api/translate/summaries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  })
  await ensureOk(response, '摘要翻译失败')
  return (await response.json()) as SummaryTranslationResponse
}

export async function fetchTask(apiFetch: ApiFetch, taskId: number): Promise<TaskInfo | null> {
  const response = await apiFetch(`/api/tasks/${taskId}`)
  if (!response.ok) return null
  return (await response.json()) as TaskInfo
}

export async function createWorkflowTaskRequest(apiFetch: ApiFetch, selectionSetId: number): Promise<TaskInfo> {
  const response = await apiFetch('/api/tasks/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selection_set_id: selectionSetId }),
  })
  await ensureOk(response, '创建任务失败')
  return (await response.json()) as TaskInfo
}

export async function startDownloadTaskRequest(apiFetch: ApiFetch, taskId: number): Promise<TaskInfo> {
  const response = await apiFetch(`/api/tasks/${taskId}/download`, { method: 'POST' })
  await ensureOk(response, '下载启动失败')
  return (await response.json()) as TaskInfo
}

export async function startExtractTaskRequest(apiFetch: ApiFetch, taskId: number): Promise<TaskInfo> {
  const response = await apiFetch(`/api/tasks/${taskId}/extract`, { method: 'POST' })
  await ensureOk(response, '解析启动失败')
  return (await response.json()) as TaskInfo
}

export async function createReportRequest(apiFetch: ApiFetch, selectionSetId: number): Promise<ReportCreateResponse> {
  const response = await apiFetch('/api/reports/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selection_set_id: selectionSetId }),
  })
  await ensureOk(response, '创建报告失败')
  return (await response.json()) as ReportCreateResponse
}

export async function fetchOutlineTemplatesRequest(apiFetch: ApiFetch, reportId: number): Promise<ReportOutlineTemplate[]> {
  const response = await apiFetch(`/api/reports/${reportId}/outline/templates`)
  await ensureOk(response, '推荐目录模板失败')
  const data = (await response.json()) as { templates?: ReportOutlineTemplate[] }
  return data.templates ?? []
}

export async function applyOutlineTemplateRequest(apiFetch: ApiFetch, reportId: number, outline: ReportOutlineNode[]): Promise<ReportSection[]> {
  const response = await apiFetch(`/api/reports/${reportId}/outline/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outline }),
  })
  await ensureOk(response, '应用目录模板失败')
  const data = (await response.json()) as { sections?: ReportSection[] }
  return data.sections ?? []
}


export async function updateSectionTitleRequest(apiFetch: ApiFetch, reportId: number, sectionId: number, title: string) {
  await apiFetch(`/api/reports/${reportId}/sections/${sectionId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function saveSectionContentRequest(apiFetch: ApiFetch, reportId: number, sectionId: number, contentMd: string) {
  const response = await apiFetch(`/api/reports/${reportId}/sections/${sectionId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content_md: contentMd }),
  })
  await ensureOk(response, '保存失败')
}

export async function generateSectionRequest(apiFetch: ApiFetch, reportId: number, sectionId: number): Promise<{ content_md: string }> {
  const response = await apiFetch(`/api/reports/${reportId}/sections/${sectionId}/generate`, { method: 'POST' })
  await ensureOk(response, '生成失败')
  return (await response.json()) as { content_md: string }
}

export async function generateFullReportRequest(apiFetch: ApiFetch, reportId: number): Promise<{ ok?: boolean; count?: number }> {
  const response = await apiFetch(`/api/reports/${reportId}/generate_all`, { method: 'POST' })
  await ensureOk(response, '整篇生成失败')
  return (await response.json()) as { ok?: boolean; count?: number }
}

export async function exportReportRequest(apiFetch: ApiFetch, reportId: number, format: 'md' | 'docx' | 'pdf') {
  const response = await apiFetch(`/api/reports/${reportId}/export?format=${format}`, { method: 'POST' })
  await ensureOk(response, '导出失败')
  await response.json()
}
