/**
 * Drag-to-reorder for a list of items, using native HTML5 drag events.
 *
 * Native drag avoids pulling in a DnD library for what is a single interaction.
 * The reorder preview happens during dragover so the row visibly moves under
 * the cursor; the commit callback fires once on drop.
 */

import { useCallback, useRef, useState } from 'react'

export function useDragOrder<T>(
  items: T[],
  getKey: (item: T) => string | number,
  onCommit: (ordered: T[]) => void,
) {
  // Working copy while a drag is in flight; null when idle
  const [draft, setDraft] = useState<T[] | null>(null)
  const dragKey = useRef<string | number | null>(null)

  const current = draft ?? items

  const onDragStart = useCallback((item: T) => (e: React.DragEvent) => {
    dragKey.current = getKey(item)
    setDraft(items)
    e.dataTransfer.effectAllowed = 'move'
    // Firefox requires data to be set for the drag to begin
    e.dataTransfer.setData('text/plain', String(getKey(item)))
  }, [items, getKey])

  const onDragOver = useCallback((target: T) => (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'

    const activeKey = dragKey.current
    if (activeKey == null) return

    setDraft(prev => {
      const list = prev ?? items
      const from = list.findIndex(i => getKey(i) === activeKey)
      const to = list.findIndex(i => getKey(i) === getKey(target))
      if (from === -1 || to === -1 || from === to) return list

      const next = [...list]
      const [moved] = next.splice(from, 1)
      next.splice(to, 0, moved)
      return next
    })
  }, [items, getKey])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const ordered = draft
    dragKey.current = null
    setDraft(null)

    if (!ordered) return
    // Only persist when the order actually changed
    const changed = ordered.some((item, i) => getKey(item) !== getKey(items[i]))
    if (changed) onCommit(ordered)
  }, [draft, items, getKey, onCommit])

  const onDragEnd = useCallback(() => {
    dragKey.current = null
    setDraft(null)
  }, [])

  const isDragging = useCallback(
    (item: T) => dragKey.current != null && getKey(item) === dragKey.current,
    [getKey],
  )

  /** Spread onto each draggable element. */
  const dragProps = useCallback((item: T) => ({
    draggable: true,
    onDragStart: onDragStart(item),
    onDragOver: onDragOver(item),
    onDrop,
    onDragEnd,
  }), [onDragStart, onDragOver, onDrop, onDragEnd])

  return { items: current, dragProps, isDragging, isActive: draft !== null }
}
