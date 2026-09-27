/**
 * Column visibility management with persistence.
 * Lets traders hide columns they don't use, reclaiming horizontal space.
 */

import { useCallback, useState } from 'react'

export interface ColumnDef {
  key: string
  label: string
  required?: boolean  // Cannot be hidden
}

export function useColumns(storageKey: string, columns: ColumnDef[]) {
  const [hidden, setHidden] = useState<Set<string>>(() => {
    const stored = localStorage.getItem(storageKey)
    return stored ? new Set(JSON.parse(stored)) : new Set()
  })

  const persist = useCallback((next: Set<string>) => {
    setHidden(next)
    localStorage.setItem(storageKey, JSON.stringify([...next]))
  }, [storageKey])

  const toggle = useCallback((key: string) => {
    const col = columns.find(c => c.key === key)
    if (col?.required) return
    const next = new Set(hidden)
    next.has(key) ? next.delete(key) : next.add(key)
    persist(next)
  }, [hidden, columns, persist])

  const reset = useCallback(() => persist(new Set()), [persist])

  const isVisible = useCallback((key: string) => !hidden.has(key), [hidden])

  return { hidden, toggle, reset, isVisible, hiddenCount: hidden.size }
}
