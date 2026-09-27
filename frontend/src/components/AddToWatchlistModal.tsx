/**
 * Add-to-watchlist picker.
 *
 * Opened by the star on Trending/Scanner. Three jobs in one place:
 *   1. Create a new list and drop the token straight into it
 *   2. Toggle membership across existing lists (a token can be in several)
 *   3. Reorder lists by dragging — the same order used everywhere else
 *
 * Membership is a checkbox rather than a one-way "add" so the star can also
 * undo a mistake without a separate trip to the Watchlist page.
 */

import { useEffect, useRef, useState } from 'react'
import { useDragOrder } from '../hooks/useDragOrder'
import type { useWatchlist } from '../hooks/useWatchlist'
import type { useWatchlists } from '../hooks/useWatchlists'
import type { RankedToken } from '../types/scanner'
import { Icons } from './ui/Icon'
import { Alert, Badge, Button, Modal, Spinner, Ticker } from './ui'

export function AddToWatchlistModal({ token, onClose, lists, watchlist }: {
  token: RankedToken | null
  onClose: () => void
  lists: ReturnType<typeof useWatchlists>
  watchlist: ReturnType<typeof useWatchlist>
}) {
  const [name, setName] = useState('')
  const [busyId, setBusyId] = useState<number | 'new' | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Reset the draft name whenever a different token is picked
  useEffect(() => { setName('') }, [token])

  const drag = useDragOrder(lists.lists, l => l.id, lists.reorder)

  if (!token) return null

  const memberIds = watchlist.listIdsFor(token.chain, token.token_address)

  const createAndAdd = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setBusyId('new')
    const created = await lists.create(trimmed)
    if (created) {
      await watchlist.addTo(created.id, token)
      setName('')
    }
    setBusyId(null)
    inputRef.current?.focus()
  }

  const toggleMembership = async (listId: number) => {
    setBusyId(listId)
    if (memberIds.has(listId)) {
      await watchlist.removeFromList(listId, token.chain, token.token_address)
    } else {
      await watchlist.addTo(listId, token)
    }
    setBusyId(null)
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Add to watchlist"
      subtitle={`${token.symbol} · ${token.name}`}
      footer={
        <div className="flex items-center justify-between gap-3">
          <span className="text-2xs text-slate-500 dark:text-slate-400">
            {memberIds.size === 0
              ? 'Not on any list yet'
              : `On ${memberIds.size} list${memberIds.size > 1 ? 's' : ''}`}
          </span>
          <Button size="sm" onClick={onClose}>Done</Button>
        </div>
      }
    >
      {/* Create */}
      <div className="flex gap-2">
        <input
          ref={inputRef}
          autoFocus
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && createAndAdd()}
          placeholder="New watchlist name…"
          className="input flex-1"
        />
        <Button
          variant="primary"
          icon={<Icons.Plus size={13} />}
          onClick={createAndAdd}
          loading={busyId === 'new'}
          disabled={!name.trim()}
        >
          Create list
        </Button>
      </div>

      {lists.error && <div className="mt-2"><Alert tone="danger">{lists.error}</Alert></div>}

      {/* Existing lists */}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-2xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Your lists
          </span>
          {lists.lists.length > 1 && (
            <span className="text-2xs text-slate-400 dark:text-slate-500">Drag to reorder</span>
          )}
        </div>

        {lists.isLoading ? (
          <div className="flex justify-center py-6">
            <Spinner size={18} className="text-brand-500" />
          </div>
        ) : drag.items.length === 0 ? (
          <p className="py-4 text-center text-xs text-slate-500 dark:text-slate-400">
            No lists yet. Name one above to get started.
          </p>
        ) : (
          <div className="max-h-[240px] overflow-y-auto -mx-1 px-1 space-y-1">
            {drag.items.map(list => {
              const isMember = memberIds.has(list.id)
              return (
                <div
                  key={list.id}
                  {...drag.dragProps(list)}
                  onClick={() => toggleMembership(list.id)}
                  className={`group flex items-center gap-2.5 px-2.5 h-10 rounded-md cursor-pointer
                              border transition-colors duration-150
                              ${isMember
                                ? 'border-brand-300 dark:border-brand-500/40 bg-brand-50 dark:bg-brand-500/10'
                                : 'border-edge-light dark:border-edge-dark hover:border-brand-300 dark:hover:border-brand-500/30'}
                              ${drag.isDragging(list) ? 'opacity-40' : ''}`}
                >
                  <span
                    className="shrink-0 cursor-grab active:cursor-grabbing
                               text-slate-300 dark:text-slate-600
                               group-hover:text-slate-400 dark:group-hover:text-slate-500"
                    title="Drag to reorder"
                    onClick={e => e.stopPropagation()}
                  >
                    <Icons.Grip size={13} />
                  </span>

                  <span className={`w-4 h-4 rounded-sm border flex items-center justify-center shrink-0
                                   ${isMember
                                     ? 'bg-brand-500 border-brand-500 text-white'
                                     : 'border-slate-300 dark:border-slate-600'}`}>
                    {busyId === list.id
                      ? <Spinner size={10} />
                      : isMember && <Icons.Check size={11} />}
                  </span>

                  <span className="flex-1 min-w-0 text-xs font-medium text-slate-800 dark:text-slate-100 truncate">
                    {list.name}
                  </span>

                  <Badge tone="neutral">{list.item_count}</Badge>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <p className="mt-3 text-2xs text-slate-400 dark:text-slate-500">
        <Ticker symbol={token.symbol} className="font-medium text-slate-500 dark:text-slate-400" />
        {' '}can sit on multiple lists at once.
      </p>
    </Modal>
  )
}
