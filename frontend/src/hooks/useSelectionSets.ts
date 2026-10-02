import { useCallback, useMemo, useState } from 'react'
import { deleteSelectionSetRequest, fetchSelectionSetPapers, fetchSelectionSetReports, fetchSelectionSets } from '../api'
import { filterAndSortSelectionSets, type SelectionSort } from '../reportUtils'
import type { ArxivItem, ExistingReport, ExistingSelectionSet } from '../types'

type UseSelectionSetsOptions = {
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
  onError: (message: string) => void
  getActiveSelectionSetId: () => number | null
  onActiveSelectionSetDeleted: () => void
}

export function useSelectionSets({ apiFetch, onError, getActiveSelectionSetId, onActiveSelectionSetDeleted }: UseSelectionSetsOptions) {
  const [existingSets, setExistingSets] = useState<ExistingSelectionSet[]>([])
  const [expandedSetId, setExpandedSetId] = useState<number | null>(null)
  const [existingSetDetails, setExistingSetDetails] = useState<Record<number, ArxivItem[]>>({})
  const [existingSetReports, setExistingSetReports] = useState<Record<number, ExistingReport[]>>({})
  const [selectionFilter, setSelectionFilter] = useState('')
  const [selectionSort, setSelectionSort] = useState<SelectionSort>('newest')

  const visibleSelectionSets = useMemo(
    () => filterAndSortSelectionSets(existingSets, selectionFilter, selectionSort),
    [existingSets, selectionFilter, selectionSort],
  )

  const fetchExistingSelectionSets = useCallback(async () => {
    try {
      setExistingSets(await fetchSelectionSets(apiFetch))
    } catch {
      // ignore
    }
  }, [apiFetch])

  const toggleExistingSet = useCallback(async (selectionSetId: number) => {
    if (expandedSetId === selectionSetId) {
      setExpandedSetId(null)
      return
    }
    setExpandedSetId(selectionSetId)
    try {
      if (!existingSetDetails[selectionSetId]) {
        const data = await fetchSelectionSetPapers(apiFetch, selectionSetId)
        setExistingSetDetails((prev) => ({ ...prev, [selectionSetId]: data }))
      }
      const reports = await fetchSelectionSetReports(apiFetch, selectionSetId)
      setExistingSetReports((prev) => ({ ...prev, [selectionSetId]: reports }))
    } catch {
      // ignore
    }
  }, [apiFetch, expandedSetId, existingSetDetails])

  const deleteExistingSet = useCallback(async (selectionSetId: number) => {
    try {
      await deleteSelectionSetRequest(apiFetch, selectionSetId)
      if (getActiveSelectionSetId() === selectionSetId) onActiveSelectionSetDeleted()
      setExistingSetDetails((prev) => {
        const next = { ...prev }
        delete next[selectionSetId]
        return next
      })
      setExistingSetReports((prev) => {
        const next = { ...prev }
        delete next[selectionSetId]
        return next
      })
      if (expandedSetId === selectionSetId) setExpandedSetId(null)
      await fetchExistingSelectionSets()
    } catch (e) {
      onError(e instanceof Error ? e.message : '未知错误')
    }
  }, [apiFetch, expandedSetId, fetchExistingSelectionSets, getActiveSelectionSetId, onActiveSelectionSetDeleted, onError])

  const resetSelectionSets = useCallback(() => {
    setExistingSets([])
    setExpandedSetId(null)
    setExistingSetDetails({})
    setExistingSetReports({})
    setSelectionFilter('')
    setSelectionSort('newest')
  }, [])

  return {
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
  }
}
