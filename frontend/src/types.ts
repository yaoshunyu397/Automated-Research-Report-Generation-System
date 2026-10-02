export type ArxivItem = {
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  pdf_url: string
  published?: string | null
  updated?: string | null
  title_zh?: string | null
  abstract_zh?: string | null
  has_pdf?: boolean
  has_parsed_text?: boolean
  has_translation?: boolean
  local_pdf_url?: string | null
  translation_url?: string | null
}

export type ArxivSearchResponse = {
  query: string
  total: number
  items: ArxivItem[]
}


export type SearchOptions = {
  yearFrom: string
  yearTo: string
  anyKeywords: string
}

export type SearchHistoryItem = SearchOptions & {
  id: string
  query: string
  searchedAt: string
}

export type SelectionSetResponse = {
  selection_set_id: number
  name: string
  count: number
  query?: string | null
}

export type ReportCreateResponse = {
  report_id: number
  selection_set_id: number
  title: string
}

export type ReportSection = {
  id: number
  parent_id: number | null
  order_index: number
  title: string
  content_md: string
}

export type ReportOutlineNode = {
  title: string
  children?: ReportOutlineNode[]
}

export type ReportOutlineTemplate = {
  template_id: number
  name: string
  description: string
  outline: ReportOutlineNode[]
}

export type TaskInfo = {
  task_id: number
  selection_set_id: number
  status: string
  step: string
  progress: number
  message?: string | null
}

export type PaperStatus = {
  arxiv_id: string
  downloaded: boolean
  parsed: boolean
  translated: boolean
  local_pdf_url?: string | null
  translation_url?: string | null
}

export type ExistingSelectionSet = {
  selection_set_id: number
  name: string
  query?: string | null
  count: number
  created_at?: string | null
}

export type ExistingReport = {
  report_id: number
  selection_set_id: number
  title: string
  section_count: number
  filled_section_count: number
  created_at?: string | null
  updated_at?: string | null
}

export type AuthUser = {
  id: number
  username: string
}

export type AuthResponse = {
  token: string
  user: AuthUser
}

export type CurrentPage = 'search' | 'selection' | 'report'

export type ViewerState = {
  type: 'pdf' | 'translation' | 'report'
  title: string
  url?: string
  content?: string
  objectUrl?: string
}
