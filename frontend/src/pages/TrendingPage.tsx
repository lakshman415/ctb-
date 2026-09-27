/**
 * Trending — primary discovery surface.
 *
 * Features: keyboard nav (j/k/Enter/w), watchlist stars, column visibility,
 * sortable columns, signal derivation, responsive card fallback on small screens.
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
import { getTrendingTokens } from '../services/api'
import type { RankedToken } from '../types/scanner'

const CHAINS = [
  { value: 'all', label: 'All' },
  { value: 'solana', label: 'SOL' },
  { value: 'ethereum', label: 'ETH' },
  { value: 'bsc', label: 'BNB' },
  { value: 'base', label: 'Base' },
  { value: 'robinhood', label: 'Robin' },
] as const

const INTERVALS = [
  { value: '5m', label: '5m' }, { value: '30m', label: '30m' },
  { value: '1h', label: '1h' }, { value: '6h', label: '6h' }, { value: '24h', label: '24h' },
] as const

const COLUMNS: ColumnDef[] = [
  { key: 'token', label: 'Token', required: true },
  { key: 'chain', label: 'Chain' },
  { key: 'market_cap', label: 'Market Cap' },
  { key: 'volume_24h', label: 'Volume' },
  { key: 'liquidity', label: 'Liquidity' },
  { key: 'price_change_1h', label: '1h Change' },
  { key: 'price_change_24h', label: '24h Change' },
  { key: 'buy_sell_ratio', label: 'B/S Ratio' },
  { key: 'txns', label: 'Transactions' },
  { key: 'signal', label: 'Signal' },
]

type SortKey = 'rank' | 'market_cap' | 'volume_24h' | 'liquidity' | 'buy_sell_ratio' | 'price_change_1h' | 'price_change_24h'

interface Filters { mcapMin: string; mcapMax: string; liqMin: string; volMin: string; bsMin: string }
const EMPTY: Filters = { mcapMin: '', mcapMax: '', liqMin: '', volMin: '', bsMin: '' }

export function TrendingPage() {
  const [chain, setChain] = useState('all')
  const [interval, setInterval] = useState('24h')
  const [tokens, setTokens] = useState<RankedToken[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [sortKey, setSortKey] = useState<SortKey>('rank')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [search, setSearch] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)

  const cols = useColumns('ctb-trending-cols', COLUMNS)
  const watchlist = useWatchlist()
  const lists = useWatchlists()

  // Token awaiting a list choice — the star opens the picker rather than
  // guessing which list the user meant.
  const [pickerToken, setPickerToken] = useState<RankedToken | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true); setError(null)
    try {
      const r = await getTrendingTokens(chain, 50, interval)
      setTokens(r.tokens)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally { setIsLoading(false) }
  }, [chain, interval])

  useEffect(() => { fetchData() }, [fetchData])

  const visible = useMemo(() => {
    const n = (s: string, d = 0) => Number(s) || d
    let out = tokens.filter(t =>
      (t.market_cap ?? 0) >= n(filters.mcapMin) &&
      (t.market_cap ?? 0) <= n(filters.mcapMax, Infinity) &&
      (t.liquidity ?? 0) >= n(filters.liqMin) &&
      (t.volume_24h ?? 0) >= n(filters.volMin) &&
      (t.buy_sell_ratio ?? 0) >= n(filters.bsMin)
    )
    if (search.trim()) {
      const q = search.toLowerCase()
      out = out.filter(t => t.symbol.toLowerCase().includes(q) || t.name.toLowerCase().includes(q))
    }
    return [...out].sort((a, b) => {
      const av = (a[sortKey] ?? 0) as number, bv = (b[sortKey] ?? 0) as number
      return sortDir === 'asc' ? av - bv : bv - av
    })
  }, [tokens, filters, search, sortKey, sortDir])

  // Keyboard navigation
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
    else { setSortKey(k); setSortDir(k === 'rank' ? 'asc' : 'desc') }
  }

  const activeFilters = Object.values(filters).filter(Boolean).length

  return (
    <div className="flex flex-col h-full">
      {/* ═══ TOOLBAR ═══ */}
      <div className="shrink-0 bg-surface-base dark:bg-surface-dark-raised
                      border-b border-edge-light dark:border-edge-dark">
        <div className="flex items-center gap-3 px-4 lg:px-5 h-12 overflow-x-auto">
          <Segmented options={CHAINS as never} value={chain} onChange={setChain} />
          <div className="w-px h-5 bg-edge-light dark:bg-edge-dark shrink-0" />
          <Segmented options={INTERVALS as never} value={interval} onChange={setInterval} />

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

          {/* Column visibility */}
          <Dropdown trigger={
            <Button size="sm" variant="secondary" icon={<Icons.Dashboard size={13} />}
              title="Show/hide columns">
              {cols.hiddenCount > 0 && <span className="text-2xs">{COLUMNS.length - cols.hiddenCount}</span>}
            </Button>
          }>
            <DropdownLabel>Visible Columns</DropdownLabel>
            {COLUMNS.map(c => (
              <DropdownItem key={c.key} checked={cols.isVisible(c.key)} onClick={() => cols.toggle(c.key)}>
                <span className={c.required ? 'opacity-50' : ''}>{c.label}</span>
              </DropdownItem>
            ))}
            {cols.hiddenCount > 0 && (
              <>
                <DropdownDivider />
                <DropdownItem onClick={cols.reset}>Show all</DropdownItem>
              </>
            )}
          </Dropdown>

          <Button size="sm" variant={filtersOpen ? 'primary' : 'secondary'}
            icon={<Icons.Filter size={13} />} onClick={() => setFiltersOpen(o => !o)}>
            <span className="hidden sm:inline">Filters</span>
            {activeFilters > 0 && <span className="px-1 rounded bg-white/25 text-2xs">{activeFilters}</span>}
          </Button>

          <Button size="sm" variant="ghost" icon={<Icons.Refresh size={13} />}
            onClick={fetchData} loading={isLoading} title="Refresh" />
        </div>

        {/* Filter drawer */}
        {filtersOpen && (
          <div className="px-4 lg:px-5 py-3 border-t border-edge-light dark:border-edge-dark
                          bg-surface-subtle dark:bg-surface-dark-base animate-slide-down">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              <Field label="MCap Min" v={filters.mcapMin} ph="500000" set={v => setFilters(f => ({ ...f, mcapMin: v }))} />
              <Field label="MCap Max" v={filters.mcapMax} ph="10000000" set={v => setFilters(f => ({ ...f, mcapMax: v }))} />
              <Field label="Liq Min" v={filters.liqMin} ph="30000" set={v => setFilters(f => ({ ...f, liqMin: v }))} />
              <Field label="Vol Min" v={filters.volMin} ph="100000" set={v => setFilters(f => ({ ...f, volMin: v }))} />
              <Field label="B/S Min" v={filters.bsMin} ph="1.0" set={v => setFilters(f => ({ ...f, bsMin: v }))} />
            </div>
            <div className="flex flex-wrap items-center gap-1.5 mt-3">
              <span className="text-2xs text-slate-400 dark:text-slate-500 mr-1">Presets</span>
              <Preset label="Small caps" onClick={() => setFilters({ ...EMPTY, mcapMin: '500000', mcapMax: '10000000', liqMin: '30000', volMin: '100000' })} />
              <Preset label="Mid caps" onClick={() => setFilters({ ...EMPTY, mcapMin: '10000000', mcapMax: '100000000', liqMin: '100000' })} />
              <Preset label="High volume" onClick={() => setFilters({ ...EMPTY, volMin: '1000000' })} />
              <Preset label="Strong buys" onClick={() => setFilters({ ...EMPTY, bsMin: '1.5' })} />
              {activeFilters > 0 && (
                <Button size="sm" variant="danger" className="ml-auto" onClick={() => setFilters(EMPTY)}>Clear</Button>
              )}
            </div>
          </div>
        )}
      </div>

      {error && <div className="px-5 pt-3"><Alert tone="danger">{error}<button onClick={fetchData} className="ml-2 underline font-medium">Retry</button></Alert></div>}

      {/* ═══ TABLE (lg+) ═══ */}
      <div className="flex-1 overflow-auto hidden lg:block">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-10 pl-5">#</th>
              <th className="w-8" />
              <th className="min-w-[150px]">Token</th>
              {cols.isVisible('chain') && <th className="w-16">Chain</th>}
              {cols.isVisible('market_cap') && <Th k="market_cap" sk={sortKey} sd={sortDir} on={toggleSort}>MCap</Th>}
              {cols.isVisible('volume_24h') && <Th k="volume_24h" sk={sortKey} sd={sortDir} on={toggleSort}>Volume</Th>}
              {cols.isVisible('liquidity') && <Th k="liquidity" sk={sortKey} sd={sortDir} on={toggleSort}>Liquidity</Th>}
              {cols.isVisible('price_change_1h') && <Th k="price_change_1h" sk={sortKey} sd={sortDir} on={toggleSort}>1h</Th>}
              {cols.isVisible('price_change_24h') && <Th k="price_change_24h" sk={sortKey} sd={sortDir} on={toggleSort}>24h</Th>}
              {cols.isVisible('buy_sell_ratio') && <Th k="buy_sell_ratio" sk={sortKey} sd={sortDir} on={toggleSort}>B/S</Th>}
              {cols.isVisible('txns') && <th className="text-right">Txns</th>}
              {cols.isVisible('signal') && <th className="w-24">Signal</th>}
              <th className="w-8 pr-5" />
            </tr>
          </thead>
          <tbody>
            {isLoading && tokens.length === 0 ? (
              Array.from({ length: 12 }).map((_, i) => <SkeletonRow key={i} cols={12} />)
            ) : visible.length === 0 ? (
              <tr><td colSpan={12}>
                <EmptyState icon={<Icons.Inbox size={32} />}
                  title={tokens.length === 0 ? 'No trending tokens' : 'No matches'}
                  description={tokens.length === 0
                    ? 'GMGN returned nothing for this chain and window. Try another combination.'
                    : `${tokens.length} loaded, none match your filters or search.`}
                  action={activeFilters > 0 || search
                    ? <Button size="sm" onClick={() => { setFilters(EMPTY); setSearch('') }}>Clear filters</Button>
                    : <Button size="sm" icon={<Icons.Refresh size={13} />} onClick={fetchData}>Refresh</Button>} />
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

      {/* ═══ CARDS (< lg) ═══ */}
      <div className="flex-1 overflow-y-auto lg:hidden p-3 space-y-2">
        {isLoading && tokens.length === 0 ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="surface rounded-lg p-3 space-y-2">
              <div className="skeleton h-4 w-24" /><div className="skeleton h-3 w-full" />
            </div>
          ))
        ) : visible.length === 0 ? (
          <EmptyState icon={<Icons.Inbox size={28} />} title="No tokens" />
        ) : (
          visible.map((t, i) => (
            <MobileCard key={`${t.pair_address}-${i}`} token={t} pos={i + 1}
              watched={watchlist.isWatched(t.chain, t.token_address)}
              onWatch={() => setPickerToken(t)} />
          ))
        )}
      </div>

      {/* ═══ STATUS ═══ */}
      <div className="shrink-0 flex items-center justify-between px-4 lg:px-5 h-8
                      border-t border-edge-light dark:border-edge-dark
                      bg-surface-base dark:bg-surface-dark-raised
                      text-2xs text-slate-500 dark:text-slate-400">
        <span className="truncate">
          Sort: <span className="text-slate-700 dark:text-slate-300 font-medium">{sortKey.replace(/_/g, ' ')}</span> {sortDir === 'asc' ? '↑' : '↓'}
          {watchlist.items.length > 0 && <span className="ml-3">{watchlist.items.length} watched</span>}
        </span>
        <span className="shrink-0">GMGN · {interval}</span>
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

// ─── Sortable header ───────────────────────────────────────

function Th({ children, k, sk, sd, on }: {
  children: React.ReactNode; k: SortKey; sk: SortKey; sd: 'asc' | 'desc'; on: (k: SortKey) => void
}) {
  const active = sk === k
  return (
    <th className="sortable text-right" onClick={() => on(k)}>
      <span className="inline-flex items-center gap-1 flex-row-reverse">
        {children}
        {active && <span className="text-brand-500">{sd === 'asc' ? <Icons.ArrowUp size={10} /> : <Icons.ArrowDown size={10} />}</span>}
      </span>
    </th>
  )
}

// ─── Desktop row ───────────────────────────────────────────

function Row({ token, pos, index, focused, cols, watched, onWatch }: {
  token: RankedToken; pos: number; index: number; focused: boolean
  cols: ReturnType<typeof useColumns>; watched: boolean; onWatch: () => void
}) {
  const url = dexUrl(token.chain, token.pair_address)
  const c1 = fmtPct(token.price_change_1h), c24 = fmtPct(token.price_change_24h)
  const txns = (token.buys ?? 0) + (token.sells ?? 0)
  const bs = token.buy_sell_ratio
  const sig = signal(token)

  return (
    <tr data-row-index={index}
      className={`group cursor-pointer ${focused ? 'bg-brand-50 dark:bg-brand-500/10 ring-1 ring-inset ring-brand-400/40' : ''}`}
      onClick={() => window.open(url, '_blank', 'noopener')}>
      <td className="pl-5 text-2xs font-mono tabular text-slate-400 dark:text-slate-500">{pos}</td>
      <td onClick={e => e.stopPropagation()}>
        <WatchStar active={watched} onClick={e => { e.stopPropagation(); onWatch() }} />
      </td>
      <td>
        <div className="flex flex-col leading-tight">
          <Ticker symbol={token.symbol}
            className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors" />
          <span className="text-2xs text-slate-500 dark:text-slate-500 truncate max-w-[130px]">{token.name}</span>
        </div>
      </td>
      {cols.isVisible('chain') && <td><ChainBadge chain={token.chain} /></td>}
      {cols.isVisible('market_cap') && <td className="td-num">{fmtUsd(token.market_cap)}</td>}
      {cols.isVisible('volume_24h') && <td className="td-num">{fmtUsd(token.volume_24h)}</td>}
      {cols.isVisible('liquidity') && <td className="td-num">{fmtUsd(token.liquidity)}</td>}
      {cols.isVisible('price_change_1h') && (
        <td className={`td-num ${c1.tone === 'up' ? 'val-up' : c1.tone === 'down' ? 'val-down' : 'val-muted'}`}>{c1.text}</td>
      )}
      {cols.isVisible('price_change_24h') && (
        <td className={`td-num ${c24.tone === 'up' ? 'val-up' : c24.tone === 'down' ? 'val-down' : 'val-muted'}`}>{c24.text}</td>
      )}
      {cols.isVisible('buy_sell_ratio') && (
        <td className={`td-num ${bs == null ? 'val-muted' : bs >= 1.5 ? 'val-up' : bs < 1 ? 'val-down' : ''}`}>
          {bs?.toFixed(2) ?? '—'}
        </td>
      )}
      {cols.isVisible('txns') && <td className="td-num text-slate-500 dark:text-slate-400">{txns > 0 ? fmtNum(txns) : '—'}</td>}
      {cols.isVisible('signal') && <td>{sig && <Badge tone={sig.tone}>{sig.label}</Badge>}</td>}
      <td className="pr-5">
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400">
          <Icons.ExternalLink size={13} />
        </span>
      </td>
    </tr>
  )
}

// ─── Mobile card ───────────────────────────────────────────

function MobileCard({ token, pos, watched, onWatch }: {
  token: RankedToken; pos: number; watched: boolean; onWatch: () => void
}) {
  const url = dexUrl(token.chain, token.pair_address)
  const c24 = fmtPct(token.price_change_24h)
  const sig = signal(token)

  return (
    <div className="surface rounded-lg p-3 group" onClick={() => window.open(url, '_blank', 'noopener')}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xs font-mono text-slate-400 w-4">{pos}</span>
        <Ticker symbol={token.symbol} className="font-semibold text-slate-900 dark:text-slate-100" />
        <ChainBadge chain={token.chain} />
        {sig && <Badge tone={sig.tone}>{sig.label}</Badge>}
        <div className="flex-1" />
        <span className={`text-sm font-mono tabular font-semibold ${c24.tone === 'up' ? 'val-up' : 'val-down'}`}>
          {c24.text}
        </span>
        <div onClick={e => e.stopPropagation()}>
          <WatchStar active={watched} onClick={e => { e.stopPropagation(); onWatch() }} />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-2xs">
        <MobileMetric label="MCap" value={fmtUsd(token.market_cap)} />
        <MobileMetric label="Volume" value={fmtUsd(token.volume_24h)} />
        <MobileMetric label="Liquidity" value={fmtUsd(token.liquidity)} />
      </div>
    </div>
  )
}

function MobileMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-slate-400 dark:text-slate-500">{label}</div>
      <div className="font-mono tabular text-slate-700 dark:text-slate-200 font-medium">{value}</div>
    </div>
  )
}

// ─── Signal derivation ─────────────────────────────────────

function signal(t: RankedToken): { label: string; tone: 'success' | 'warning' | 'danger' | 'brand' } | null {
  const vol = t.volume_24h ?? 0, liq = t.liquidity ?? 0
  const bs = t.buy_sell_ratio ?? 0, ch1 = t.price_change_1h ?? 0
  const lmc = t.liquidity_mcap_ratio ?? 0

  if (lmc > 0 && lmc < 0.02) return { label: 'Thin liq', tone: 'danger' }
  if (liq > 0 && vol / liq > 20) return { label: 'Vol spike', tone: 'warning' }
  if (bs >= 2 && ch1 > 5) return { label: 'Momentum', tone: 'success' }
  if (bs >= 1.5) return { label: 'Buy pressure', tone: 'success' }
  if (ch1 > 20) return { label: 'Breakout', tone: 'brand' }
  if (ch1 < -15) return { label: 'Dumping', tone: 'danger' }
  return null
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

// ─── Filter helpers ────────────────────────────────────────

function Field({ label, v, ph, set }: { label: string; v: string; ph: string; set: (v: string) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input type="number" value={v} placeholder={ph} onChange={e => set(e.target.value)} className="input input-mono" />
    </div>
  )
}

function Preset({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="px-2 h-6 rounded text-2xs font-medium
                 bg-surface-base dark:bg-surface-dark-overlay
                 border border-edge-light-strong dark:border-edge-dark-strong
                 text-slate-600 dark:text-slate-400
                 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400
                 transition-colors duration-150">
      {label}
    </button>
  )
}
