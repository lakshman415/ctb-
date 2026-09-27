/**
 * Keyboard navigation for data tables.
 *
 * Bindings:
 *   j / ↓     next row
 *   k / ↑     previous row
 *   Enter     open focused row
 *   w         add focused row to watchlist
 *   /         focus search input
 *   Esc       clear focus
 *
 * Why: traders keep hands on keyboard. Mouse-only tables are slow.
 */

import { useCallback, useEffect, useState } from 'react'

interface Options {
  itemCount: number
  onOpen?: (index: number) => void
  onWatch?: (index: number) => void
  onSearch?: () => void
  enabled?: boolean
}

export function useKeyboardNav({ itemCount, onOpen, onWatch, onSearch, enabled = true }: Options) {
  const [focusedIndex, setFocusedIndex] = useState(-1)

  // Reset focus when the list shrinks below the current index
  useEffect(() => {
    if (focusedIndex >= itemCount) setFocusedIndex(itemCount - 1)
  }, [itemCount, focusedIndex])

  const handler = useCallback((e: KeyboardEvent) => {
    if (!enabled) return

    // Don't hijack keys while typing
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
      if (e.key === 'Escape') target.blur()
      return
    }

    switch (e.key) {
      case 'j':
      case 'ArrowDown':
        e.preventDefault()
        setFocusedIndex(i => Math.min(i + 1, itemCount - 1))
        break

      case 'k':
      case 'ArrowUp':
        e.preventDefault()
        setFocusedIndex(i => Math.max(i - 1, 0))
        break

      case 'Enter':
        if (focusedIndex >= 0 && onOpen) {
          e.preventDefault()
          onOpen(focusedIndex)
        }
        break

      case 'w':
        if (focusedIndex >= 0 && onWatch) {
          e.preventDefault()
          onWatch(focusedIndex)
        }
        break

      case '/':
        if (onSearch) {
          e.preventDefault()
          onSearch()
        }
        break

      case 'Escape':
        setFocusedIndex(-1)
        break

      case 'g':
        // gg → jump to top (vim-style)
        setFocusedIndex(0)
        break

      case 'G':
        setFocusedIndex(itemCount - 1)
        break
    }
  }, [enabled, itemCount, focusedIndex, onOpen, onWatch, onSearch])

  useEffect(() => {
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handler])

  // Scroll focused row into view
  useEffect(() => {
    if (focusedIndex < 0) return
    const el = document.querySelector(`[data-row-index="${focusedIndex}"]`)
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [focusedIndex])

  return { focusedIndex, setFocusedIndex }
}
