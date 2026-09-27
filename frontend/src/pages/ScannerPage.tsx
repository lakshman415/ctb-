/**
 * Scanner — full market sweep from our own scoring engine.
 * Differs from Trending: this is OUR scored data across all indexed tokens.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AddToWatchlistModal } from '../components/AddToWatchlistModal'
import { useColumns, type ColumnDef } from '../hooks/useColumns'
import { useKeyboardNav } from '../hooks/useKeyboardNav'
import { useWatchlist } from '../hooks/useWatchlist'
import { useWatchlists } from '../hooks/useWatchlists'
import { Icons } from '../components/ui/Icon'
import {
  Alert, Badge, Button, Dropdown, DropdownDivider, DropdownItem, DropdownLabel,
  EmptyState, KeyboardHints, Segmented, SkeletonRow, Ticker, WatchStar,
  dexUrl, fmtNum, fmtPct, fmtUsd,
} from '../components/ui'
import { getAllTokens, triggerScan } from '../services/api'
import type { RankedToken } from '../types/scanner'

type SortKey = 'score' | 'market_cap' | 'volume_24h' | 'liquidity' | 'buy_sell_ratio' | 'price_change_24h'

const CATEGORIES = [
  { value: 'all', label: 'All' },
  { value: 'early', label: 'Early' },
  { value: 'mid', label: 'Mid' },
  { value: 'large', label: 'Large' },
  { value: 'uncategorized', label: 'Other' },
] as const

const COLUMNS: ColumnDef[] = [
  { key: 'score', label: 'Score', required: true },
  { key: 'chain', label: 'Chain' },
  { key: 'category', label: 'Tier' },
  { key: 'market_cap', label: 'Market Cap' },
  { key: 'volume_24h', label: 'Volume' },
  { key: 'liquidity', label: 'Liquidity' },
  { key: 'lmc', label: 'Liq/MCap' },
  { key: 'buy_sell_ratio', label: 'B/S Ratio' },
  { key: 'price_change_24h', label: '24h Change' },
  { key: 'txns', label: 'Transactions' },
]

export function ScannerPage() {
  const [tokens, setTokens] = useState<RankedToken[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isScanning, setIsScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [meta, setMeta] = useState({ fetched: 0, scanned: '' })
  const searchRef = useRef<HTMLInputElement>(null)

  const cols = useColumns('ctb-scanner-cols', COLUMNS)
  const watchlist = useWatchlist()
  const lists = useWatchlists()

  // Star opens the list picker instead of assuming a destination list
  const [pickerToken, setPickerToken] = useState<RankedToken | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true); setError(null)
    try {
      const r = await getAllTokens()
      setTokens(r.tokens)
      setMeta({ fetched: r.total_pairs_fetched, scanned: r.scanned_at })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally { setIsLoading(false) }
  }, [])

  const scan = async () => {
    setIsScanning(true)
    try { await triggerScan(); await load() }
    catch (err) { setError(err instanceof Error ? err.message : 'Scan failed') }
    finally { setIsScanning(false) }
  }

  useEffect(() => { load() }, [load])

  const visible = useMemo(() => {
    let out = tokens
    if (category !== 'all') out = out.filter(t => t.category === category)
    if (search.trim()) {
      const q = search.toLowerCase()
      out = out.filter(t => t.symbol.toLowerCase().includes(q) || t.name.toLowerCase().includes(q))
    }
    return [...out].sort((a, b) => {
      const av = (a[sortKey] ?? 0) as number, bv = (b[sortKey] ?? 0) as number
      return sortDir === 'asc' ? av - bv : bv - av
    })
  }, [tokens, category, search, sortKey, sortDir])

  const { focusedIndex } = useKeyboardNav({
    itemCount: visible.length,
    onOpen: i => {
      const t = visible[i]
      if (t) window.open(dexUrl(t.chain, t.pair_address), '_blank', 'noopener')
    },
    onWatch: i => { const t = visible[i]; if (t) setPickerToken(t) },
    onSearch: () => searchRef.current?.focus(),
  })

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(k); setSortDir('desc') }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="shrink-0 flex items-center gap-3 px-4 lg:px-5 h-12 overflow-x-auto
                      bg-surface-base dark:bg-surface-dark-raised
                      border-b border-edge-light dark:border-edge-dark">
        <Segmented options={CATEGORIES as never} value={category} onChange={setCategory} />

        <div className="relative w-44 shrink-0">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
            <Icons.Search size={13} />
          </span>
          <input ref={searchRef} value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search  /" className="input pl-8" />
        </div>

        <div className="flex-1 min-w-4" />
        <KeyboardHints />

        <span className="text-2xs text-slate-500 dark:text-slate-400 tabular shrink-0">
          {isLoading ? '…' : `${visible.length}/${tokens.length}`}
        </span>

        <Dropdown trigger={
          <Button size="sm" variant="secondary" icon={<Icons.Dashboard size={13} />} title="Columns">
            {cols.hiddenCount > 0 && <span className="text-2xs">{COLUMNS.length - cols.hiddenCount}</span>}
          </Button>
        }>
          <DropdownLabel>Visible Columns</DropdownLabel>
          {COLUMNS.map(c => (
            <DropdownItem key={c.key} checked={cols.isVisible(c.key)} onClick={() => cols.toggle(c.key)}>
              <span className={c.required ? 'opacity-50' : ''}>{c.label}</span>
            </DropdownItem>
          ))}
          {cols.hiddenCount > 0 && <><DropdownDivider /><DropdownItem onClick={cols.reset}>Show all</DropdownItem></>}
        </Dropdown>

        <Button size="sm" variant="ghost" icon={<Icons.Refresh size={13} />}
          onClick={load} loading={isLoading && !isScanning} title="Reload cached" />
        <Button size="sm" variant="primary" icon={<Icons.Radar size={13} />} onClick={scan} loading={isScanning}>
          <span className="hidden sm:inline">Run Scan</span>
        </Button>
      </div>

      {error && <div className="px-5 pt-3"><Alert tone="danger">{error}</Alert></div>}

      {/* Table (lg+) */}
      <div className="flex-1 overflow-auto hidden lg:block">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-10 pl-5">#</th>
              <th className="w-8" />
              <Th k="score" sk={sortKey} sd={sortDir} on={toggleSort} w="w-16">Score</Th>
              <th className="min-w-[150px]">Token</th>
              {cols.isVisible('chain') && <th className="w-16">Chain</th>}
              {cols.isVisible('category') && <th className="w-16">Tier</th>}
              {cols.isVisible('market_cap') && <Th k="market_cap" sk={sortKey} sd={sortDir} on={toggleSort}>MCap</Th>}
              {cols.isVisible('volume_24h') && <Th k="volume_24h" sk={sortKey} sd={sortDir} on={toggleSort}>Volume</Th>}
              {cols.isVisible('liquidity') && <Th k="liquidity" sk={sortKey} sd={sortDir} on={toggleSort}>Liquidity</Th>}
              {cols.isVisible('lmc') && <th className="text-right">L/MC</th>}
              {cols.isVisible('buy_sell_ratio') && <Th k="buy_sell_ratio" sk={sortKey} sd={sortDir} on={toggleSort}>B/S</Th>}
              {cols.isVisible('price_change_24h') && <Th k="price_change_24h" sk={sortKey} sd={sortDir} on={toggleSort}>24h</Th>}
              {cols.isVisible('txns') && <th className="text-right">Txns</th>}
              <th className="w-8 pr-5" />
            </tr>
          </thead>
          <tbody>
            {isLoading && tokens.length === 0 ? (
              Array.from({ length: 14 }).map((_, i) => <SkeletonRow key={i} cols={13} />)
            ) : visible.length === 0 ? (
              <tr><td colSpan={13}>
                <EmptyState icon={<Icons.Radar size={32} />}
                  title={tokens.length === 0 ? 'No scan data yet' : 'No matches'}
                  description={tokens.length === 0
                    ? 'Run a scan to sweep all supported chains and score every token found.'
                    : 'Adjust the category filter or search term.'}
                  action={tokens.length === 0
                    ? <Button size="sm" variant="primary" icon={<Icons.Radar size={13} />} onClick={scan} loading={isScanning}>Run first scan</Button>
                    : <Button size="sm" onClick={() => { setSearch(''); setCategory('all') }}>Clear filters</Button>} />
              </td></tr>
            ) : (
              visible.map((t, i) => (
                <Row key={`${t.pair_address}-${i}`} token={t} pos={i + 1} index={i}
                  focused={focusedIndex === i} cols={cols}
                  watched={watchlist.isWatched(t.chain, t.token_address)}
                  onWatch={() => setPickerToken(t)} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Cards (< lg) */}
      <div className="flex-1 overflow-y-auto lg:hidden p-3 space-y-2">
        {visible.map((t, i) => (
          <div key={`${t.pair_address}-${i}`} className="surface rounded-lg p-3 group"
            onClick={() => window.open(dexUrl(t.chain, t.pair_address), '_blank', 'noopener')}>
            <div className="flex items-center gap-2 mb-2">
              <ScorePill score={t.score} />
              <Ticker symbol={t.symbol} className="font-semibold text-slate-900 dark:text-slate-100" />
              <span className="text-2xs text-slate-500">{t.chain.slice(0, 4).toUpperCase()}</span>
              <div className="flex-1" />
              <div onClick={e => e.stopPropagation()}>
                <WatchStar active={watchlist.isWatched(t.chain, t.token_address)}
                  onClick={e => { e.stopPropagation(); setPickerToken(t) }} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-2xs">
              <div><div className="text-slate-400">MCap</div><div className="font-mono tabular text-slate-700 dark:text-slate-200">{fmtUsd(t.market_cap)}</div></div>
              <div><div className="text-slate-400">Volume</div><div className="font-mono tabular text-slate-700 dark:text-slate-200">{fmtUsd(t.volume_24h)}</div></div>
              <div><div className="text-slate-400">Liq</div><div className="font-mono tabular text-slate-700 dark:text-slate-200">{fmtUsd(t.liquidity)}</div></div>
            </div>
          </div>
        ))}
      </div>

      {/* Status */}
      <div className="shrink-0 flex items-center justify-between px-4 lg:px-5 h-8
                      border-t border-edge-light dark:border-edge-dark
                      bg-surface-base dark:bg-surface-dark-raised
                      text-2xs text-slate-500 dark:text-slate-400">
        <span>{meta.fetched > 0 && `${meta.fetched} pairs swept`}</span>
        <span>{meta.scanned && `Last scan ${new Date(meta.scanned).toLocaleTimeString()}`}</span>
      </div>

      <AddToWatchlistModal
        token={pickerToken}
        onClose={() => setPickerToken(null)}
        lists={lists}
        watchlist={watchlist}
      />
    </div>
  )
}

function Th({ children, k, sk, sd, on, w }: {
  children: React.ReactNode; k: SortKey; sk: SortKey; sd: 'asc' | 'desc'; on: (k: SortKey) => void; w?: string
}) {
  const active = sk === k
  return (
    <th className={`sortable text-right ${w ?? ''}`} onClick={() => on(k)}>
      <span className="inline-flex items-center gap-1 flex-row-reverse">
        {children}
        {active && <span className="text-brand-500">{sd === 'asc' ? <Icons.ArrowUp size={10} /> : <Icons.ArrowDown size={10} />}</span>}
      </span>
    </th>
  )
}

function Row({ token, pos, index, focused, cols, watched, onWatch }: {
  token: RankedToken; pos: number; index: number; focused: boolean
  cols: ReturnType<typeof useColumns>; watched: boolean; onWatch: () => void
}) {
  const url = dexUrl(token.chain, token.pair_address)
  const ch = fmtPct(token.price_change_24h)
  const bs = token.buy_sell_ratio, lmc = token.liquidity_mcap_ratio
  const txns = (token.buys ?? 0) + (token.sells ?? 0)

  return (
    <tr data-row-index={index}
      className={`group cursor-pointer ${focused ? 'bg-brand-50 dark:bg-brand-500/10 ring-1 ring-inset ring-brand-400/40' : ''}`}
      onClick={() => window.open(url, '_blank', 'noopener')}>
      <td className="pl-5 text-2xs font-mono tabular text-slate-400 dark:text-slate-500">{pos}</td>
      <td onClick={e => e.stopPropagation()}>
        <WatchStar active={watched} onClick={e => { e.stopPropagation(); onWatch() }} />
      </td>
      <td className="text-right"><ScorePill score={token.score} /></td>
      <td>
        <div className="flex flex-col leading-tight">
          <Ticker symbol={token.symbol}
            className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors" />
          <span className="text-2xs text-slate-500 dark:text-slate-500 truncate max-w-[130px]">{token.name}</span>
        </div>
      </td>
      {cols.isVisible('chain') && <td className="text-2xs font-medium text-slate-500 dark:text-slate-400">{token.chain.slice(0, 4).toUpperCase()}</td>}
      {cols.isVisible('category') && <td className="text-2xs text-slate-500 dark:text-slate-400 capitalize">{token.category}</td>}
      {cols.isVisible('market_cap') && <td className="td-num">{fmtUsd(token.market_cap)}</td>}
      {cols.isVisible('volume_24h') && <td className="td-num">{fmtUsd(token.volume_24h)}</td>}
      {cols.isVisible('liquidity') && <td className="td-num">{fmtUsd(token.liquidity)}</td>}
      {cols.isVisible('lmc') && (
        <td className={`td-num ${lmc == null ? 'val-muted' : lmc >= 0.1 ? 'val-up' : lmc < 0.02 ? 'val-down' : ''}`}>
          {lmc != null ? `${(lmc * 100).toFixed(1)}%` : '—'}
        </td>
      )}
      {cols.isVisible('buy_sell_ratio') && (
        <td className={`td-num ${bs == null ? 'val-muted' : bs >= 1.5 ? 'val-up' : bs < 1 ? 'val-down' : ''}`}>
          {bs?.toFixed(2) ?? '—'}
        </td>
      )}
      {cols.isVisible('price_change_24h') && (
        <td className={`td-num ${ch.tone === 'up' ? 'val-up' : ch.tone === 'down' ? 'val-down' : 'val-muted'}`}>{ch.text}</td>
      )}
      {cols.isVisible('txns') && <td className="td-num text-slate-500 dark:text-slate-400">{txns > 0 ? fmtNum(txns) : '—'}</td>}
      <td className="pr-5">
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400">
          <Icons.ExternalLink size={13} />
        </span>
      </td>
    </tr>
  )
}

function ScorePill({ score }: { score: number }) {
  const tone = score >= 60 ? 'success' : score >= 45 ? 'brand' : score >= 30 ? 'warning' : 'neutral'
  return <Badge tone={tone}>{score.toFixed(0)}</Badge>
}
