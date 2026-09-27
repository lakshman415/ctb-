/**
 * Journal — trade review, learnings, and pre-trade checklist.
 *
 * Design decisions:
 * - Tabs instead of accordions: traders switch between these constantly, accordion
 *   collapse/expand adds a click every time
 * - Trade rows are compact table rows, not cards (density matters for 50+ trades)
 * - Notes inline-expand rather than modal (keeps context visible)
 * - Learnings/Checklist as cards because they're read-once-per-session, not scanned
 */

import { useCallback, useEffect, useState } from 'react'
import { Icons } from '../components/ui/Icon'
import {
  Alert, Badge, Button, EmptyState, Panel, PanelHeader,
  Segmented, Spinner, StatCard, Ticker, fmtUsd,
} from '../components/ui'
import {
  createJournalEntry, deleteJournalEntry, getJournalEntries,
  getTradeNotes, getWalletActivity, type JournalEntry,
} from '../services/api'

// Wallet addresses are placeholders. Replace with your own, or better, load them
// from the backend (which reads WALLET_* from .env) via an API call.
const CHAINS = [
  { value: 'sol', label: 'Solana', wallet: 'YOUR_SOLANA_WALLET_ADDRESS' },
  { value: 'eth', label: 'Ethereum', wallet: 'YOUR_ETHEREUM_WALLET_ADDRESS' },
  { value: 'bsc', label: 'BSC', wallet: 'YOUR_BSC_WALLET_ADDRESS' },
  { value: 'base', label: 'Base', wallet: 'YOUR_BASE_WALLET_ADDRESS' },
  { value: 'robinhood', label: 'Robinhood', wallet: 'YOUR_ROBINHOOD_WALLET_ADDRESS' },
]

const TABS = [
  { value: 'trades', label: 'Trade Review' },
  { value: 'learnings', label: 'Learnings' },
  { value: 'checklist', label: 'Checklist' },
] as const

export function JournalPage() {
  const [tab, setTab] = useState<string>('trades')

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="shrink-0 flex items-center gap-4 px-4 sm:px-5 h-12
                      bg-surface-base dark:bg-surface-dark-raised
                      border-b border-edge-light dark:border-edge-dark">
        <Segmented options={TABS as never} value={tab} onChange={setTab} />
        <div className="flex-1" />
        <span className="hidden md:inline text-2xs text-slate-500 dark:text-slate-400">
          {tab === 'trades' && 'Review past trades and record what happened'}
          {tab === 'learnings' && 'Insights you\'ve gained from trading'}
          {tab === 'checklist' && 'Review before every trade'}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'trades' && <TradeReview />}
        {tab === 'learnings' && <NotesGrid category="learning" title="Learnings"
          subtitle="What you've figured out from experience"
          placeholder="e.g. Volume spike before price move is the strongest entry signal" />}
        {tab === 'checklist' && <NotesGrid category="cheatsheet" title="Pre-Trade Checklist"
          subtitle="Run through this before every entry"
          placeholder="e.g. Verify Liq/MCap ratio is above 2%" />}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// TRADE REVIEW
// ═══════════════════════════════════════════════════════════

interface Trade {
  symbol: string
  costUsd: number
  isBuy: boolean
  pnl: number | null
  pnlPct: number | null
  txHash: string
  timestamp: number
}

function TradeReview() {
  const [chain, setChain] = useState('robinhood')
  const [wallet, setWallet] = useState('')
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 7)
    return d.toISOString().split('T')[0]
  })
  const [trades, setTrades] = useState<Trade[]>([])
  const [notes, setNotes] = useState<Record<string, { id: number; text: string }>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasFetched, setHasFetched] = useState(false)

  const activeChain = CHAINS.find(c => c.value === chain)!

  useEffect(() => {
    setWallet(activeChain.wallet)
    setTrades([])
    setHasFetched(false)
  }, [chain, activeChain.wallet])

  const fetch = useCallback(async () => {
    if (!wallet.trim()) return
    setIsLoading(true)
    setError(null)
    try {
      const days = Math.ceil((Date.now() - new Date(fromDate).getTime()) / 86400000)
      const limit = Math.min(Math.max(days * 5, 20), 100)
      const [data, noteMap] = await Promise.all([
        getWalletActivity(chain, limit, wallet.trim()),
        getTradeNotes(),
      ])
      const acts = ((data as { activities?: unknown[] })?.activities ?? []) as Record<string, unknown>[]
      const fromTs = new Date(fromDate).getTime() / 1000
      setTrades(parseTrades(acts.filter(a => Number(a.timestamp ?? 0) >= fromTs)))
      setNotes(noteMap)
      setHasFetched(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch trades')
    } finally {
      setIsLoading(false)
    }
  }, [chain, wallet, fromDate])

  const saveNote = async (txHash: string, text: string, symbol: string) => {
    await createJournalEntry({ category: 'trade_note', text, tx_hash: txHash, token_symbol: symbol, chain })
    setNotes(await getTradeNotes())
  }

  const closed = trades.filter(t => t.pnl !== null)
  const wins = closed.filter(t => t.pnl! >= 0)
  const losses = closed.filter(t => t.pnl! < 0)
  const totalPnl = closed.reduce((s, t) => s + t.pnl!, 0)
  const journaled = trades.filter(t => notes[t.txHash]).length

  return (
    <div className="p-4 sm:p-5 space-y-4">
      {/* Query builder */}
      <Panel>
        <PanelHeader title="Load Trades" subtitle="Select chain, verify wallet, pick start date" />
        <div className="panel-body space-y-3">
          <div>
            <label className="label">Chain</label>
            <Segmented options={CHAINS} value={chain} onChange={setChain} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px_auto] gap-3 items-end">
            <div>
              <label className="label">Wallet Address</label>
              <input value={wallet} onChange={e => setWallet(e.target.value)} className="input input-mono" />
            </div>
            <div>
              <label className="label">From Date</label>
              <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="input" />
            </div>
            <Button variant="primary" onClick={fetch} loading={isLoading} disabled={!wallet.trim()}>
              Load Trades
            </Button>
          </div>
        </div>
      </Panel>

      {error && <Alert tone="danger">{error}</Alert>}

      {/* Metrics */}
      {closed.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Net P&L" value={fmtUsd(totalPnl, false)} tone={totalPnl >= 0 ? 'up' : 'down'} />
          <StatCard label="Win Rate" value={`${((wins.length / closed.length) * 100).toFixed(0)}%`}
            delta={`${wins.length}W / ${losses.length}L`} />
          <StatCard label="Avg Win" value={wins.length ? fmtUsd(wins.reduce((s, t) => s + t.pnl!, 0) / wins.length, false) : '—'} tone="up" />
          <StatCard label="Avg Loss" value={losses.length ? fmtUsd(losses.reduce((s, t) => s + t.pnl!, 0) / losses.length, false) : '—'} tone="down" />
        </div>
      )}

      {/* Trade table */}
      {trades.length > 0 ? (
        <Panel>
          <PanelHeader
            title="Trades"
            subtitle={`${trades.length} transactions · ${journaled} journaled`}
            actions={
              journaled < trades.length
                ? <Badge tone="warning">{trades.length - journaled} need notes</Badge>
                : <Badge tone="success">All journaled</Badge>
            }
          />
          <div className="table-wrap max-h-[440px]">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-16 pl-4">Side</th>
                  <th className="min-w-[100px]">Token</th>
                  <th className="text-right">Size</th>
                  <th className="text-right">P&L</th>
                  <th className="text-right w-20">Return</th>
                  <th className="w-24">Date</th>
                  <th className="w-16 pr-4 text-center">Note</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <TradeRow key={t.txHash || i} trade={t} note={notes[t.txHash]} onSave={saveNote} />
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : hasFetched && !isLoading ? (
        <Panel>
          <EmptyState
            icon={<Icons.Wallet size={32} />}
            title="No trades in this period"
            description="Try an earlier start date or a different chain."
          />
        </Panel>
      ) : !hasFetched && !isLoading ? (
        <Panel>
          <EmptyState
            icon={<Icons.Wallet size={32} />}
            title="Load your trade history"
            description="Select a chain and date range above, then click Load Trades to review your performance."
          />
        </Panel>
      ) : null}

      {/* Loss patterns */}
      {losses.length > 0 && (
        <Panel className="border-danger-200 dark:border-danger-500/20">
          <PanelHeader title="Loss Patterns" subtitle="Recurring mistakes worth addressing" />
          <div className="panel-body space-y-2">
            {losses.slice(0, 8).map((l, i) => (
              <div key={i} className="flex items-start gap-2.5 text-xs">
                <Badge tone="danger" className="shrink-0 mt-px">
                  <Ticker symbol={l.symbol} />
                </Badge>
                <span className="text-slate-600 dark:text-slate-300">
                  <span className="font-mono tabular val-down">{fmtUsd(l.pnl, false)}</span>
                  {' '}({l.pnlPct!.toFixed(0)}%) —{' '}
                  {l.pnlPct! < -70 ? 'Held through a major drawdown. Consider a hard stop at -30%.'
                    : l.pnlPct! < -40 ? 'Entry was likely late in the move. Wait for pullbacks.'
                    : 'Controlled loss. Risk management working.'}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  )
}

// ─── Trade Row ─────────────────────────────────────────────

function TradeRow({ trade, note, onSave }: {
  trade: Trade
  note?: { id: number; text: string }
  onSave: (txHash: string, text: string, symbol: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')

  const submit = () => {
    if (!input.trim()) return
    onSave(trade.txHash, input.trim(), trade.symbol)
    setInput('')
    setOpen(false)
  }

  return (
    <>
      <tr className="cursor-pointer group" onClick={() => setOpen(o => !o)}>
        <td className="pl-4">
          <Badge tone={trade.isBuy ? 'success' : 'danger'}>{trade.isBuy ? 'BUY' : 'SELL'}</Badge>
        </td>
        <td className="font-semibold text-slate-900 dark:text-slate-100">
          <Ticker symbol={trade.symbol} />
        </td>
        <td className="td-num">{fmtUsd(trade.costUsd, false)}</td>
        <td className={`td-num ${trade.pnl == null ? 'val-muted' : trade.pnl >= 0 ? 'val-up' : 'val-down'}`}>
          {trade.pnl != null ? fmtUsd(trade.pnl, false) : '—'}
        </td>
        <td className={`td-num ${trade.pnlPct == null ? 'val-muted' : trade.pnlPct >= 0 ? 'val-up' : 'val-down'}`}>
          {trade.pnlPct != null ? `${trade.pnlPct >= 0 ? '+' : ''}${trade.pnlPct.toFixed(0)}%` : '—'}
        </td>
        <td className="text-2xs text-slate-500 dark:text-slate-400">
          {trade.timestamp ? new Date(trade.timestamp * 1000).toLocaleDateString() : '—'}
        </td>
        <td className="pr-4 text-center">
          {note
            ? <span className="text-success-500 inline-flex"><Icons.Check size={14} /></span>
            : <span className="text-slate-300 dark:text-slate-600 group-hover:text-brand-500 inline-flex transition-colors">
                <Icons.Plus size={14} />
              </span>}
        </td>
      </tr>
      {open && (
        <tr className="bg-surface-subtle dark:bg-surface-dark-base">
          <td colSpan={7} className="px-4 py-3">
            {note && (
              <div className="mb-2 px-3 py-2 rounded-md bg-success-50 dark:bg-success-500/8
                              border border-success-200 dark:border-success-500/20">
                <p className="text-xs text-slate-700 dark:text-slate-200 italic">{note.text}</p>
              </div>
            )}
            <div className="flex gap-2">
              <input
                autoFocus
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && submit()}
                onClick={e => e.stopPropagation()}
                placeholder="What was your thesis? What went right or wrong?"
                className="input flex-1"
              />
              <Button variant="primary" size="md" onClick={submit} disabled={!input.trim()}>
                {note ? 'Update' : 'Save'}
              </Button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ═══════════════════════════════════════════════════════════
// NOTES GRID (Learnings / Checklist)
// ═══════════════════════════════════════════════════════════

function NotesGrid({ category, title, subtitle, placeholder }: {
  category: string; title: string; subtitle: string; placeholder: string
}) {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      setEntries(await getJournalEntries(category))
    } catch { /* silent */ }
    setIsLoading(false)
  }, [category])

  useEffect(() => { load() }, [load])

  const add = async () => {
    if (!input.trim()) return
    setSaving(true)
    await createJournalEntry({ category, text: input.trim() })
    setInput('')
    setSaving(false)
    load()
  }

  const remove = async (id: number) => {
    await deleteJournalEntry(id)
    load()
  }

  return (
    <div className="p-4 sm:p-5 space-y-4">
      <Panel>
        <PanelHeader title={title} subtitle={subtitle} actions={<Badge tone="neutral">{entries.length}</Badge>} />
        <div className="panel-body">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && add()}
              placeholder={placeholder}
              className="input flex-1"
            />
            <Button variant="primary" icon={<Icons.Plus size={13} />} onClick={add} loading={saving} disabled={!input.trim()}>
              Add
            </Button>
          </div>
        </div>
      </Panel>

      {isLoading ? (
        <div className="flex justify-center py-12"><Spinner size={20} className="text-brand-500" /></div>
      ) : entries.length === 0 ? (
        <Panel>
          <EmptyState
            icon={category === 'learning' ? <Icons.Bulb size={32} /> : <Icons.Clipboard size={32} />}
            title={`No ${category === 'learning' ? 'learnings' : 'checklist items'} yet`}
            description="Add your first one above. These persist in the database."
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {entries.map(e => (
            <div key={e.id}
              className="surface rounded-lg p-3.5 group hover:border-brand-300 dark:hover:border-brand-500/30
                         transition-colors duration-150">
              <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{e.text}</p>
              <div className="flex items-center justify-between mt-2.5">
                <span className="text-2xs text-slate-400 dark:text-slate-500">
                  {new Date(e.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
                <button
                  onClick={() => remove(e.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity
                             text-slate-400 hover:text-danger-500 dark:hover:text-danger-400"
                  title="Delete"
                >
                  <Icons.X size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Parsing ───────────────────────────────────────────────

function parseTrades(activities: Record<string, unknown>[]): Trade[] {
  return activities.map(a => {
    const token = (a.token as Record<string, unknown>) ?? {}
    const costUsd = Number(a.cost_usd ?? 0)
    const buyCostUsd = Number(a.buy_cost_usd ?? 0)
    const isBuy = String(a.event_type ?? '') === 'buy'
    const pnl = !isBuy && buyCostUsd > 0 ? costUsd - buyCostUsd : null
    return {
      symbol: String(token.symbol ?? '?'),
      costUsd,
      isBuy,
      pnl,
      pnlPct: pnl !== null && buyCostUsd > 0 ? (pnl / buyCostUsd) * 100 : null,
      txHash: String(a.tx_hash ?? ''),
      timestamp: Number(a.timestamp ?? 0),
    }
  })
}
