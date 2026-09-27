/**
 * Watchlist collections — create, rename, delete, reorder.
 *
 * Reordering applies optimistically so dragging feels instant, then persists.
 * The server response is authoritative, so a failed save snaps back.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  createWatchlist, deleteWatchlist, getWatchlists,
  renameWatchlist, reorderWatchlists, type Watchlist,
} from '../services/api'

export function useWatchlists() {
  const [lists, setLists] = useState<Watchlist[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLists(await getWatchlists())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlists')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const create = useCallback(async (name: string): Promise<Watchlist | null> => {
    try {
      const created = await createWatchlist(name)
      await load()
      setError(null)
      return created
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create watchlist')
      return null
    }
  }, [load])

  const rename = useCallback(async (id: number, name: string) => {
    try {
      await renameWatchlist(id, name)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not rename watchlist')
    }
  }, [load])

  const remove = useCallback(async (id: number) => {
    try {
      await deleteWatchlist(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete watchlist')
    }
  }, [load])

  /** Persist a reordered list. Applies optimistically, reverts on failure. */
  const reorder = useCallback(async (ordered: Watchlist[]) => {
    const previous = lists
    setLists(ordered)
    try {
      setLists(await reorderWatchlists(ordered.map(l => l.id)))
    } catch (err) {
      setLists(previous)
      setError(err instanceof Error ? err.message : 'Could not save the new order')
    }
  }, [lists])

  return { lists, isLoading, error, create, rename, remove, reorder, reload: load }
}
