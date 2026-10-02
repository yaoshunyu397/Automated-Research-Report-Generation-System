import type { ExistingSelectionSet, ReportSection } from './types'

export type OutlineRow = { sec: ReportSection; depth: number }
export type SelectionSort = 'newest' | 'oldest' | 'name' | 'count'

export function buildOutlineRows(sections: ReportSection[]): OutlineRow[] {
  const byParent = new Map<number | null, ReportSection[]>()
  for (const section of sections) {
    const arr = byParent.get(section.parent_id) ?? []
    arr.push(section)
    byParent.set(section.parent_id, arr)
  }
  for (const arr of byParent.values()) arr.sort((a, b) => a.order_index - b.order_index)

  const rows: OutlineRow[] = []
  const walk = (parent: number | null, depth: number) => {
    for (const sec of byParent.get(parent) ?? []) {
      rows.push({ sec, depth })
      walk(sec.id, depth + 1)
    }
  }
  walk(null, 0)
  return rows
}

export function buildReportPreviewContentFromSections(
  sections: ReportSection[],
  draftOverride?: { sectionId: number | null; content: string },
) {
  const byParent = new Map<number | null, ReportSection[]>()
  for (const section of sections) {
    const arr = byParent.get(section.parent_id) ?? []
    arr.push(section)
    byParent.set(section.parent_id, arr)
  }
  for (const arr of byParent.values()) arr.sort((a, b) => a.order_index - b.order_index)

  const lines = ['# 调研报告', '']
  const walk = (parent: number | null, depth: number) => {
    for (const section of byParent.get(parent) ?? []) {
      const heading = '#'.repeat(Math.min(depth + 2, 6))
      const content = section.id === draftOverride?.sectionId ? draftOverride.content : section.content_md
      lines.push(`${heading} ${section.title}`)
      if (content?.trim()) lines.push('', content.trim())
      lines.push('')
      walk(section.id, depth + 1)
    }
  }
  walk(null, 0)
  return lines.join('\n').trim() + '\n'
}

export function calculateReportCompletion(sections: ReportSection[]) {
  const total = sections.length
  const filled = sections.filter((section) => section.content_md.trim()).length
  return { total, filled, percent: total ? Math.round((filled / total) * 100) : 0 }
}

export function filterAndSortSelectionSets(
  existingSets: ExistingSelectionSet[],
  selectionFilter: string,
  selectionSort: SelectionSort,
) {
  const keyword = selectionFilter.trim().toLowerCase()
  const filtered = existingSets.filter((item) => {
    if (!keyword) return true
    return item.name.toLowerCase().includes(keyword) || (item.query ?? '').toLowerCase().includes(keyword)
  })
  return [...filtered].sort((a, b) => {
    if (selectionSort === 'name') return a.name.localeCompare(b.name, 'zh-Hans-CN')
    if (selectionSort === 'count') return b.count - a.count
    const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
    const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
    return selectionSort === 'oldest' ? aTime - bTime : bTime - aTime
  })
}
