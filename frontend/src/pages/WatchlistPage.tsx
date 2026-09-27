/**
 * Watchlist — named lists of tracked tokens with live market data.
 *
 * Design decisions:
 * - Lists render as a horizontal tab strip, draggable to reorder. Order is
 *   persisted server-side so it holds across devices and reloads.
 * - The table shows live metrics, not the values captured at add time: a
 *   watchlist is only useful if it reflects the market right now.
 * - Every column sorts on click, toggling asc/desc. Default is the manual
 *   order so a hand-curated list stays as arranged until you sort it.
 * - Triggered alerts sit above everything — they're time-sensitive.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useDragOrder } from '../hooks/useDragOrder'
import { useWatchlists } from '../hooks/useWatchlists'
import { Icons } from '../components/ui/Icon'
import {
  Alert as AlertBox, Badge, Button, EmptyState, Modal, Panel, PanelHeader,
  Spinner, Ticker, dexUrl, fmtAge, fmtPct, fmtPrice, fmtUsd,
} from '../components/ui'
import {
  acknowledgeAlert, createAlert, deleteAlert, getTriggeredAlerts, getWatchlist,
  getWatchlistTokens, removeFromWatchlist, toggleAlert,
  type AlertRule, type Watchlist, type WatchlistTokenQuote,
} from '../services/api'

// Column order is fixed and deliberate: identity, size, activity, age, then
// momentum from shortest to longest window, then chain.
type SortKey =
  | 'position' | 'symbol' | 'market_cap' | 'volume_24h' | 'age_hours'
  | 'price_change_5m' | 'price_change_1h' | 'price_change_24h' | 'chain'

const COLUMNS: { key: SortKey; label: string; align: 'left' | 'right' }[] = [
  { key: 'symbol', label: 'Token', align: 'left' },
  { key: 'market_cap', label: 'MCap', align: 'right' },
  { key: 'volume_24h', label: 'Vol', align: 'right' },
  { key: 'age_hours', label: 'Age', align: 'right' },
  { key: 'price_change_5m', label: '5m', align: 'right' },
  { key: 'price_change_1h', label: '1h', align: 'right' },
  { key: 'price_change_24h', label: '24h', align: 'right' },
  { key: 'chain', label: 'Chain', align: 'left' },
]

const LAST_LIST_KEY = 'ctb-active-watchlist'

export function WatchlistPage() {
  const lists = useWatchlists()
  const [activeId, setActiveId] = useState<number | null>(null)
  const [tokens, setTokens] = useState<WatchlistTokenQuote[]>([])
  const [isLoadingTokens, setIsLoadingTokens] = useState(false)
  const [tokenError, setTokenError] = useState<string | null>(null)
  const [triggered, setTriggered] = useState<AlertRule[]>([])
  const [sortKey, setSortKey] = useState<SortKey>('position')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [renaming, setRenaming] = useState<Watchlist | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Watchlist | null>(null)
  const [alertsFor, setAlertsFor] = useState<WatchlistTokenQuote | null>(null)

  // Pick a list once loaded: last used if it still exists, else the first
  useEffect(() => {
    if (lists.isLoading || lists.lists.length === 0) return
    setActiveId(prev => {
      if (prev !== null && lists.lists.some(l => l.id === prev)) return prev
      const remembered = Number(localStorage.getItem(LAST_LIST_KEY))
      if (remembered && lists.lists.some(l => l.id === remembered)) return remembered
      return lists.lists[0].id
    })
  }, [lists.isLoading, lists.lists])

  useEffect(() => {
    if (activeId !== null) localStorage.setItem(LAST_LIST_KEY, String(activeId))
  }, [activeId])

  const loadTokens = useCallback(async (listId: number) => {
    setIsLoadingTokens(true)
    setTokenError(null)
    try {
      setTokens(await getWatchlistTokens(listId))
    } catch (err) {
      setTokenError(err instanceof Error ? err.message : 'Failed to load live prices')
      setTokens([])
    } finally {
      setIsLoadingTokens(false)
    }
  }, [])

  useEffect(() => {
    if (activeId !== null) loadTokens(activeId)
  }, [activeId, loadTokens])

  useEffect(() => {
    getTriggeredAlerts().then(setTriggered).catch(() => { /* non-critical */ })
  }, [])

  const drag = useDragOrder(lists.lists, l => l.id, lists.reorder)

  const sorted = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1
    return [...tokens].sort((a, b) => {
      if (sortKey === 'symbol' || sortKey === 'chain') {
        return a[sortKey].localeCompare(b[sortKey]) * dir
      }
      const av = a[sortKey], bv = b[sortKey]
      // Missing values sort last regardless of direction
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      return (av - bv) * dir
    })
  }, [tokens, sortKey, sortDir])

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(k)
      // Text sorts read better A→Z; numbers are most useful biggest-first
      setSortDir(k === 'symbol' || k === 'chain' ? 'asc' : 'desc')
    }
  }

  const removeToken = async (itemId: number) => {
    await removeFromWatchlist(itemId)
    if (activeId !== null) {
      await loadTokens(activeId)
      lists.reload()
    }
  }

  const dismissAlert = async (id: number) => {
    await acknowledgeAlert(id)
    setTriggered(await getTriggeredAlerts())
  }

  const activeList = lists.lists.find(l => l.id === activeId) ?? null

  if (lists.isLoading) {
    return <div className="flex justify-center pt-20"><Spinner size={22} className="text-brand-500" /></div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* ═══ LIST TABS ═══ */}
      <div className="shrink-0 bg-surface-base dark:bg-surface-dark-raised
                      border-b border-edge-light dark:border-edge-dark">
        <div className="flex items-center gap-2 px-4 sm:px-5 h-12 overflow-x-auto">
          {drag.items.length === 0 ? (
            <span className="text-xs text-slate-500 dark:text-slate-400">
              No lists yet — star a token on Trending to create one.
            </span>
          ) : (
            drag.items.map(list => (
              <button
                key={list.id}
                {...drag.dragProps(list)}
                onClick={() => setActiveId(list.id)}
                title="Click to open · drag to reorder"
                className={`group shrink-0 inline-flex items-center gap-1.5 px-2.5 h-8 rounded-md
                            border text-xs font-medium cursor-pointer
                            transition-colors duration-150
                            ${list.id === activeId
                              ? 'border-brand-400 dark:border-brand-500/50 bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300'
                              : 'border-edge-light dark:border-edge-dark text-slate-600 dark:text-slate-300 hover:border-brand-300 dark:hover:border-brand-500/30'}
                            ${drag.isDragging(list) ? 'opacity-40' : ''}`}
              >
                <span className="text-slate-300 dark:text-slate-600 group-hover:text-slate-400 cursor-grab active:cursor-grabbing">
                  <Icons.Grip size={12} />
                </span>
                {list.name}
                <span className="text-2xs tabular opacity-60">{list.item_count}</span>
              </button>
            ))
          )}

          <div className="flex-1 min-w-2" />

          {activeList && (
            <>
              <Button size="sm" variant="ghost" icon={<Icons.Pencil size={13} />}
                title="Rename list" onClick={() => setRenaming(activeList)} />
              <Button size="sm" variant="ghost" icon={<Icons.X size={13} />}
                title="Delete list" onClick={() => setConfirmDelete(activeList)} />
              <Button size="sm" variant="ghost" icon={<Icons.Refresh size={13} />}
                title="Refresh prices" loading={isLoadingTokens}
                onClick={() => loadTokens(activeList.id)} />
            </>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
        {lists.error && <AlertBox tone="danger">{lists.error}</AlertBox>}

        {/* ═══ TRIGGERED ALERTS ═══ */}
        {triggered.length > 0 && (
          <Panel className="border-warning-300 dark:border-warning-500/30">
            <PanelHeader title="Triggered Alerts" subtitle="Conditions met since your last check"
              actions={<Badge tone="warning">{triggered.length}</Badge>} />
            <div className="divide-y divide-edge-light dark:divide-edge-dark">
              {triggered.map(a => (
                <div key={a.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5">
                  <span className="text-warning-500 shrink-0"><Icons.Bell size={15} /></span>
                  <span className="flex-1 min-w-0 text-xs text-slate-600 dark:text-slate-300">
                    {a.metric.replace(/_/g, ' ')} went <span className="font-medium">{a.condition}</span>{' '}
                    <span className="font-mono tabular">{a.threshold.toLocaleString()}</span>
                    {a.triggered_value != null && (
                      <span className="text-slate-500 dark:text-slate-400">
                        {' '}— now <span className="font-mono tabular">{a.triggered_value.toLocaleString()}</span>
                      </span>
                    )}
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => dismissAlert(a.id)}>Dismiss</Button>
                </div>
              ))}
            </div>
          </Panel>
        )}

        {tokenError && (
          <AlertBox tone="danger">
            {tokenError}
            <button onClick={() => activeId && loadTokens(activeId)} className="ml-2 underline font-medium">
              Retry
            </button>
          </AlertBox>
        )}

        {/* ═══ TOKEN TABLE ═══ */}
        {activeList && (
          <Panel>
            <PanelHeader
              title={activeList.name}
              subtitle={isLoadingTokens ? 'Fetching live prices…' : `${tokens.length} token${tokens.length === 1 ? '' : 's'} · live data`}
              actions={
                sortKey !== 'position'
                  ? <Button size="sm" variant="ghost" onClick={() => { setSortKey('position'); setSortDir('asc') }}>
                      Reset sort
                    </Button>
                  : undefined
              }
            />

            {isLoadingTokens && tokens.length === 0 ? (
              <div className="flex justify-center py-12"><Spinner size={20} className="text-brand-500" /></div>
            ) : tokens.length === 0 ? (
              <EmptyState
                icon={<Icons.Star size={32} />}
                title={`"${activeList.name}" is empty`}
                description="Star a token on Trending or Scanner and pick this list to add it."
              />
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th className="w-8 pl-4" />
                      {COLUMNS.map(c => (
                        <Th key={c.key} k={c.key} sk={sortKey} sd={sortDir} on={toggleSort} align={c.align}>
                          {c.label}
                        </Th>
                      ))}
                      <th className="w-8 pr-4" />
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((t, i) => (
                      <TokenRow
                        key={t.item_id}
                        token={t}
                        pos={i + 1}
                        onRemove={() => removeToken(t.item_id)}
                        onAlerts={() => setAlertsFor(t)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        )}
      </div>

      {/* ═══ STATUS ═══ */}
      <div className="shrink-0 flex items-center justify-between px-4 sm:px-5 h-8
                      border-t border-edge-light dark:border-edge-dark
                      bg-surface-base dark:bg-surface-dark-raised
                      text-2xs text-slate-500 dark:text-slate-400">
        <span className="truncate">
          {sortKey === 'position'
            ? 'Manual order'
            : <>Sort: <span className="text-slate-700 dark:text-slate-300 font-medium">
                {COLUMNS.find(c => c.key === sortKey)?.label}</span> {sortDir === 'asc' ? '↑' : '↓'}</>}
        </span>
        <span className="shrink-0">
          {lists.lists.length} list{lists.lists.length === 1 ? '' : 's'} · DexScreener live
        </span>
      </div>

      {/* ═══ ALERTS ═══ */}
      <AlertsModal
        token={alertsFor}
        onClose={() => setAlertsFor(null)}
        onChanged={() => { if (activeId !== null) loadTokens(activeId) }}
      />

      {/* ═══ RENAME ═══ */}
      <RenameModal
        list={renaming}
        onClose={() => setRenaming(null)}
        onSave={async (name) => {
          if (renaming) await lists.rename(renaming.id, name)
          setRenaming(null)
        }}
      />

      {/* ═══ DELETE CONFIRM ═══ */}
      <Modal
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title="Delete watchlist"
        subtitle={confirmDelete?.name}
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button size="sm" onClick={() => setConfirmDelete(null)}>Cancel</Button>
            <Button size="sm" variant="danger" onClick={async () => {
              if (confirmDelete) {
                await lists.remove(confirmDelete.id)
                if (activeId === confirmDelete.id) setActiveId(null)
              }
              setConfirmDelete(null)
            }}>
              Delete list
            </Button>
          </div>
        }
      >
        <p className="text-xs text-slate-600 dark:text-slate-300">
          This removes the list and its {confirmDelete?.item_count ?? 0} token
          {confirmDelete?.item_count === 1 ? '' : 's'}, along with any alerts on them.
          Your other lists are untouched.
        </p>
      </Modal>
    </div>
  )
}

// ─── Rename modal ──────────────────────────────────────────

function RenameModal({ list, onClose, onSave }: {
  list: Watchlist | null
  onClose: () => void
  onSave: (name: string) => void
}) {
  const [name, setName] = useState('')

  useEffect(() => { setName(list?.name ?? '') }, [list])

  return (
    <Modal
      open={list !== null}
      onClose={onClose}
      title="Rename watchlist"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" variant="primary" disabled={!name.trim()} onClick={() => onSave(name.trim())}>
            Save
          </Button>
        </div>
      }
    >
      <input
        autoFocus
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && name.trim() && onSave(name.trim())}
        className="input w-full"
        placeholder="Watchlist name"
      />
    </Modal>
  )
}

// ─── Alerts modal ──────────────────────────────────────────

const METRICS = [
  { value: 'market_cap', label: 'Market Cap' },
  { value: 'price', label: 'Price' },
  { value: 'volume_24h', label: 'Volume 24h' },
  { value: 'liquidity', label: 'Liquidity' },
  { value: 'price_change_1h', label: '1h Change %' },
]

/**
 * Threshold alerts for one watched token.
 *
 * Kept in a modal rather than an expandable row so the table can stay at the
 * exact column set that matters for scanning.
 */
function AlertsModal({ token, onClose, onChanged }: {
  token: WatchlistTokenQuote | null
  onClose: () => void
  onChanged: () => void
}) {
  const [alerts, setAlerts] = useState<AlertRule[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [metric, setMetric] = useState('market_cap')
  const [condition, setCondition] = useState<'above' | 'below'>('above')
  const [threshold, setThreshold] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    if (!token) return
    setIsLoading(true)
    try {
      const items = await getWatchlist()
      setAlerts(items.find(i => i.id === token.item_id)?.alerts ?? [])
    } catch { /* non-critical */ }
    setIsLoading(false)
  }, [token])

  useEffect(() => { load() }, [load])

  if (!token) return null

  const add = async () => {
    const value = Number(threshold)
    if (!value) return
    setSaving(true)
    await createAlert({ watchlist_id: token.item_id, metric, condition, threshold: value })
    setThreshold('')
    setSaving(false)
    await load()
    onChanged()
  }

  const fmtThreshold = (m: string, v: number) =>
    m === 'price' ? fmtPrice(v) : m.includes('change') ? fmtPct(v).text : fmtUsd(v)

  return (
    <Modal
      open
      onClose={onClose}
      title="Alerts"
      subtitle={`${token.symbol} · current MCap ${fmtUsd(token.market_cap)}`}
      footer={
        <div className="flex items-center justify-end">
          <Button size="sm" onClick={onClose}>Done</Button>
        </div>
      }
    >
      {isLoading ? (
        <div className="flex justify-center py-6"><Spinner size={18} className="text-brand-500" /></div>
      ) : alerts.length > 0 ? (
        <div className="space-y-1 mb-3">
          {alerts.map(a => (
            <div key={a.id} className="flex items-center gap-2 text-xs">
              <button
                onClick={async () => { await toggleAlert(a.id); await load(); onChanged() }}
                title={a.enabled ? 'Disable' : 'Enable'}
                className={`w-8 h-4 rounded-full p-0.5 transition-colors shrink-0
                           ${a.enabled ? 'bg-brand-500' : 'bg-slate-300 dark:bg-slate-600'}`}
              >
                <div className={`w-3 h-3 rounded-full bg-white shadow-sm transition-transform
                                ${a.enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </button>
              <span className="text-slate-700 dark:text-slate-200">
                {METRICS.find(m => m.value === a.metric)?.label ?? a.metric}{' '}
                <span className="text-slate-500 dark:text-slate-400">{a.condition}</span>{' '}
                <span className="font-mono tabular font-medium">{fmtThreshold(a.metric, a.threshold)}</span>
              </span>
              {a.triggered && <Badge tone="warning">Fired</Badge>}
              <div className="flex-1" />
              <button
                onClick={async () => { await deleteAlert(a.id); await load(); onChanged() }}
                className="text-slate-400 hover:text-danger-500 transition-colors"
                title="Delete alert"
              >
                <Icons.X size={12} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
          No alerts yet. Alerts are checked after every scan.
        </p>
      )}

      <div className="flex flex-wrap items-end gap-2 pt-3 border-t border-edge-light dark:border-edge-dark">
        <div className="w-32">
          <label className="label">Metric</label>
          <select value={metric} onChange={e => setMetric(e.target.value)} className="input">
            {METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <div className="w-24">
          <label className="label">Condition</label>
          <select value={condition} onChange={e => setCondition(e.target.value as 'above' | 'below')} className="input">
            <option value="above">Above</option>
            <option value="below">Below</option>
          </select>
        </div>
        <div className="w-28">
          <label className="label">Threshold</label>
          <input
            type="number"
            value={threshold}
            onChange={e => setThreshold(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && add()}
            placeholder="1000000"
            className="input input-mono"
          />
        </div>
        <Button variant="primary" icon={<Icons.Bell size={13} />}
          onClick={add} loading={saving} disabled={!threshold}>
          Add
        </Button>
      </div>
    </Modal>
  )
}

// ─── Sortable header ───────────────────────────────────────

function Th({ children, k, sk, sd, on, align }: {
  children: React.ReactNode
  k: SortKey; sk: SortKey; sd: 'asc' | 'desc'
  on: (k: SortKey) => void
  align: 'left' | 'right'
}) {
  const active = sk === k
  return (
    <th
      className={`sortable ${align === 'right' ? 'text-right' : ''}`}
      onClick={() => on(k)}
      aria-sort={active ? (sd === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <span className={`inline-flex items-center gap-1 ${align === 'right' ? 'flex-row-reverse' : ''}`}>
        {children}
        {active && (
          <span className="text-brand-500">
            {sd === 'asc' ? <Icons.ArrowUp size={10} /> : <Icons.ArrowDown size={10} />}
          </span>
        )}
      </span>
    </th>
  )
}

// ─── Token row ─────────────────────────────────────────────

function TokenRow({ token, pos, onRemove, onAlerts }: {
  token: WatchlistTokenQuote; pos: number; onRemove: () => void; onAlerts: () => void
}) {
  const url = dexUrl(token.chain, token.pair_address)
  const c5 = fmtPct(token.price_change_5m)
  const c1 = fmtPct(token.price_change_1h)
  const c24 = fmtPct(token.price_change_24h)

  const tone = (t: 'up' | 'down' | 'neutral') =>
    t === 'up' ? 'val-up' : t === 'down' ? 'val-down' : 'val-muted'

  return (
    <tr className="group cursor-pointer" onClick={() => window.open(url, '_blank', 'noopener')}>
      <td className="pl-4 text-2xs font-mono tabular text-slate-400 dark:text-slate-500">{pos}</td>

      <td>
        <div className="flex items-center gap-1.5">
          <div className="flex flex-col leading-tight min-w-0">
            <Ticker
              symbol={token.symbol}
              className="font-semibold text-slate-900 dark:text-slate-100
                         group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors"
            />
            <span className="text-2xs text-slate-500 dark:text-slate-500 truncate max-w-[130px]">
              {token.name}
            </span>
          </div>
          {token.alert_count > 0 && (
            <span className="text-brand-500 shrink-0" title={`${token.alert_count} active alert(s)`}>
              <Icons.Bell size={11} />
            </span>
          )}
          {token.is_stale && (
            <span className="text-warning-500 shrink-0" title="Live data unavailable — showing stored values">
              <Icons.Warning size={11} />
            </span>
          )}
        </div>
      </td>

      <td className="td-num">{fmtUsd(token.market_cap)}</td>
      <td className="td-num">{fmtUsd(token.volume_24h)}</td>
      <td className="td-num text-slate-500 dark:text-slate-400">{fmtAge(token.age_hours)}</td>
      <td className={`td-num ${tone(c5.tone)}`}>{c5.text}</td>
      <td className={`td-num ${tone(c1.tone)}`}>{c1.text}</td>
      <td className={`td-num ${tone(c24.tone)}`}>{c24.text}</td>
      <td><ChainBadge chain={token.chain} /></td>

      <td className="pr-4">
        <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={e => { e.stopPropagation(); onAlerts() }}
            title="Manage alerts"
            className="p-1 rounded text-slate-400 hover:text-brand-500 transition-colors"
          >
            <Icons.Bell size={13} />
          </button>
          <button
            onClick={e => { e.stopPropagation(); onRemove() }}
            title={`Remove ${token.symbol} from this list`}
            className="p-1 rounded text-slate-400 hover:text-danger-500 transition-colors"
          >
            <Icons.X size={13} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ─── Chain badge ───────────────────────────────────────────

const CHAIN_STYLE: Record<string, string> = {
  solana: 'bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300',
  ethereum: 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300',
  bsc: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
  base: 'bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300',
  robinhood: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
}
const CHAIN_LABEL: Record<string, string> = {
  solana: 'SOL', ethereum: 'ETH', bsc: 'BNB', base: 'BASE', robinhood: 'RBH',
}

function ChainBadge({ chain }: { chain: string }) {
  return (
    <span className={`badge ${CHAIN_STYLE[chain] ?? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'}`}>
      {CHAIN_LABEL[chain] ?? chain.slice(0, 4).toUpperCase()}
    </span>
  )
}
