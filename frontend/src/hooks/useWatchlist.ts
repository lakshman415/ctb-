/**
 * Watchlist membership — shared across pages so the star icon reflects
 * membership everywhere without prop drilling.
 *
 * A token can live in several lists at once, so membership is a set of items
 * rather than a boolean. The star is lit when the token is in at least one list.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { addToWatchlist, getWatchlist, removeFromWatchlist, type WatchlistItem } from '../services/api'
import type { RankedToken } from '../types/scanner'

const key = (chain: string, address: string) => `${chain}:${address.toLowerCase()}`

export function useWatchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setItems(await getWatchlist())
    } catch { /* silent — watchlist is non-critical */ }
    setIsLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  // token key -> its items (one per list it belongs to)
  const byToken = useMemo(() => {
    const map = new Map<string, WatchlistItem[]>()
    for (const item of items) {
      const k = key(item.chain, item.token_address)
      const bucket = map.get(k)
      if (bucket) bucket.push(item)
      else map.set(k, [item])
    }
    return map
  }, [items])

  const isWatched = useCallback(
    (chain: string, address: string) => byToken.has(key(chain, address)),
    [byToken],
  )

  /** Every item for this token, one per list containing it. */
  const itemsFor = useCallback(
    (chain: string, address: string) => byToken.get(key(chain, address)) ?? [],
    [byToken],
  )

  /** Ids of the lists a token currently belongs to. */
  const listIdsFor = useCallback(
    (chain: string, address: string) =>
      new Set(
        (byToken.get(key(chain, address)) ?? [])
          .map(i => i.watchlist_id)
          .filter((id): id is number => id != null),
      ),
    [byToken],
  )

  const addTo = useCallback(async (listId: number, token: RankedToken) => {
    await addToWatchlist({
      watchlist_id: listId,
      chain: token.chain,
      token_address: token.token_address,
      pair_address: token.pair_address,
      symbol: token.symbol,
      name: token.name,
      added_price: token.price,
      added_market_cap: token.market_cap,
    })
    await load()
  }, [load])

  const removeItem = useCallback(async (itemId: number) => {
    await removeFromWatchlist(itemId)
    await load()
  }, [load])

  /** Remove a token from one specific list. */
  const removeFromList = useCallback(async (listId: number, chain: string, address: string) => {
    const target = itemsFor(chain, address).find(i => i.watchlist_id === listId)
    if (target) {
      await removeFromWatchlist(target.id)
      await load()
    }
  }, [itemsFor, load])

  return {
    items, isLoading, isWatched, itemsFor, listIdsFor,
    addTo, removeItem, removeFromList, reload: load,
  }
}
