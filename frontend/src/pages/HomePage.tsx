/**
 * Token Analysis — deep dive on a single token.
 *
 * Design decisions:
 * - Search bar is the hero: this page has one job, make it obvious
 * - Grade + key metrics above the fold, chart below, details in tabs
 * - Metrics grouped by decision: "Can I trade it?" (liquidity) vs "Should I?" (momentum)
 * - Chart embedded but not dominant — the analysis is the product, not the chart
 */

import { useState } from 'react'
import { Icons } from '../components/ui/Icon'
import {
  Alert, Badge, Button, EmptyState, Panel, PanelHeader,
  Segmented, StatCard, dexUrl, fmtAge, fmtNum, fmtPct, fmtPrice, fmtUsd,
} from '../components/ui'
import { analyzeToken } from '../services/api'
import type { TokenAnalysis } from '../types/analysis'

const CHAINS = [
  { value: 'solana', label: 'Solana' },
  { value: 'ethereum', label: 'Ethereum' },
  { value: 'bsc', label: 'BNB' },
  { value: 'base', label: 'Base' },
  { value: 'robinhood', label: 'Robinhood' },
]

export function HomePage() {
  const [address, setAddress] = useState('')
  const [chain, setChain] = useState('solana')
  const [data, setData] = useState<TokenAnalysis | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    if (!address.trim()) return
    setIsLoading(true)
    setError(null)
    setData(null)
    try {
      setData(await analyzeToken(chain, address.trim()))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* ═══ SEARCH ═══ */}
      <div className="border-b border-edge-light dark:border-edge-dark
                      bg-surface-base dark:bg-surface-dark-raised px-4 sm:px-5 py-4">
        <div className="max-w-4xl space-y-2.5">
          <Segmented options={CHAINS} value={chain} onChange={setChain} />
          <div className="flex gap-2">
            <input
              value={address}
              onChange={e => setAddress(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()}
              placeholder="Paste token contract address…"
              className="input input-mono flex-1 h-9"
            />
            <Button variant="primary" size="lg" onClick={run} loading={isLoading} disabled={!address.trim()}>
              Analyze
            </Button>
          </div>
          {error && <Alert tone="danger">{error}</Alert>}
        </div>
      </div>

      {/* ═══ RESULTS ═══ */}
      {data ? <AnalysisView data={data} /> : !isLoading && (
        <EmptyState
          icon={<Icons.Search size={36} />}
          title="Analyze any token"
          description="Paste a contract address above to get liquidity health, momentum, risk assessment, support/resistance levels, and a full technical breakdown."
        />
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// ANALYSIS VIEW
// ═══════════════════════════════════════════════════════════

function AnalysisView({ data }: { data: TokenAnalysis }) {
  const { overview, technicals, volume, transactions, price_changes } = data
  const [tab, setTab] = useState('overview')

  return (
    <div className="p-4 sm:p-5 space-y-4">
      {/* Header: identity + grade */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
              {overview.symbol}
            </h2>
            <span className="text-sm text-slate-500 dark:text-slate-400 truncate">{overview.name}</span>
            <Badge tone="neutral">{overview.chain}</Badge>
            <Badge tone="neutral">{overview.dex}</Badge>
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            <span className="text-2xs font-mono text-slate-400 dark:text-slate-500">
              {overview.token_address.slice(0, 10)}…{overview.token_address.slice(-8)}
            </span>
            {overview.dexscreener_url && (
              <a href={overview.dexscreener_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-2xs font-medium text-brand-600 dark:text-brand-400 hover:underline">
                DexScreener <Icons.ExternalLink size={11} />
              </a>
            )}
          </div>
        </div>
        <GradeCard grade={technicals.overall_grade} score={data.score} risk={technicals.risk_level} />
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatCard label="Price" value={fmtPrice(overview.price)} />
        <StatCard label="Market Cap" value={fmtUsd(overview.market_cap)} />
        <StatCard label="Liquidity" value={fmtUsd(overview.liquidity)}
          hint="Higher liquidity = lower slippage when entering/exiting" />
        <StatCard label="Volume 24h" value={fmtUsd(volume.volume_24h)} />
        <StatCard label="Liq / MCap"
          value={technicals.liquidity_mcap_ratio ? `${(technicals.liquidity_mcap_ratio * 100).toFixed(1)}%` : '—'}
          tone={technicals.liquidity_mcap_ratio && technicals.liquidity_mcap_ratio >= 0.1 ? 'up'
            : technicals.liquidity_mcap_ratio && technicals.liquidity_mcap_ratio < 0.02 ? 'down' : 'neutral'}
          hint="Below 2% often signals fake market cap or a honeypot" />
      </div>

      {/* Price changes */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <ChangeCard label="5 min" value={price_changes.change_5m} />
        <ChangeCard label="1 hour" value={price_changes.change_1h} />
        <ChangeCard label="6 hours" value={price_changes.change_6h} />
        <ChangeCard label="24 hours" value={price_changes.change_24h} />
      </div>

      {/* Signals — the most actionable part, so it goes first */}
      {technicals.key_signals.length > 0 && (
        <Panel className="border-brand-200 dark:border-brand-500/25">
          <PanelHeader title="Key Signals" subtitle="What a professional trader would notice right now" />
          <div className="panel-body space-y-2">
            {technicals.key_signals.map((s, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <span className="mt-0.5 text-brand-500 shrink-0"><Icons.Zap size={13} /></span>
                <span className="text-sm text-slate-700 dark:text-slate-200">{s}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Chart */}
      {overview.dexscreener_url && (
        <Panel>
          <PanelHeader
            title="Price Chart"
            actions={
              <a href={overview.dexscreener_url} target="_blank" rel="noopener noreferrer"
                className="btn btn-sm btn-ghost">
                Full chart <Icons.ExternalLink size={12} />
              </a>
            }
          />
          <iframe
            src={dexUrl(overview.chain, overview.pair_address, '?embed=1&theme=dark&trades=0&info=0')}
            className="w-full h-[300px] sm:h-[420px] border-0 block"
            title="Price chart"
          />
        </Panel>
      )}

      {/* Detail tabs */}
      <Panel>
        <div className="panel-header">
          <Segmented
            options={[
              { value: 'overview', label: 'Assessment' },
              { value: 'levels', label: 'S/R Levels' },
              { value: 'activity', label: 'Activity' },
            ]}
            value={tab}
            onChange={setTab}
          />
        </div>
        <div className="panel-body">
          {tab === 'overview' && <AssessmentTab technicals={technicals} />}
          {tab === 'levels' && <LevelsTab technicals={technicals} marketCap={overview.market_cap} />}
          {tab === 'activity' && <ActivityTab transactions={transactions} volume={volume} overview={overview} technicals={technicals} />}
        </div>
      </Panel>
    </div>
  )
}

// ─── Grade Card ────────────────────────────────────────────

function GradeCard({ grade, score, risk }: { grade: string | null; score: number; risk: string | null }) {
  const tone =
    grade === 'A' ? 'border-success-300 dark:border-success-500/30 bg-success-50 dark:bg-success-500/8 text-success-700 dark:text-success-400'
    : grade === 'B' ? 'border-brand-300 dark:border-brand-500/30 bg-brand-50 dark:bg-brand-500/8 text-brand-700 dark:text-brand-400'
    : grade === 'C' ? 'border-warning-300 dark:border-warning-500/30 bg-warning-50 dark:bg-warning-500/8 text-warning-700 dark:text-warning-400'
    : 'border-danger-300 dark:border-danger-500/30 bg-danger-50 dark:bg-danger-500/8 text-danger-700 dark:text-danger-400'

  return (
    <div className={`shrink-0 rounded-lg border px-5 py-3 text-center ${tone}`}>
      <div className="text-3xl font-bold leading-none">{grade ?? '?'}</div>
      <div className="text-2xs font-mono tabular mt-1.5 opacity-80">{score.toFixed(0)}/100</div>
      <div className="text-2xs uppercase tracking-wide mt-0.5 opacity-70">{risk} risk</div>
    </div>
  )
}

// ─── Change Card ───────────────────────────────────────────

function ChangeCard({ label, value }: { label: string; value: number | null }) {
  const p = fmtPct(value)
  return (
    <div className="surface rounded-lg px-3.5 py-2.5">
      <div className="text-2xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`text-lg font-semibold font-mono tabular mt-0.5
        ${p.tone === 'up' ? 'val-up' : p.tone === 'down' ? 'val-down' : 'val-muted'}`}>
        {p.text}
      </div>
    </div>
  )
}

// ─── Tabs ──────────────────────────────────────────────────

function AssessmentTab({ technicals }: { technicals: TokenAnalysis['technicals'] }) {
  const rows = [
    { label: 'Liquidity Health', value: technicals.liquidity_grade, why: 'Determines slippage and exit safety' },
    { label: 'Volume Quality', value: technicals.volume_grade, why: 'Confirms whether price action is real' },
    { label: 'Buy Pressure', value: technicals.buy_pressure_grade, why: 'Who is in control — buyers or sellers' },
    { label: 'Token Age', value: technicals.age_grade, why: 'Newer = higher risk and higher potential' },
    { label: 'Trend', value: technicals.trend_direction, why: 'Direction across multiple timeframes' },
    { label: 'Volatility', value: technicals.volatility_grade, why: 'How much price swings — affects position sizing' },
    { label: 'Momentum 1h', value: technicals.momentum_1h, why: 'Short-term direction' },
    { label: 'Risk / Reward', value: technicals.risk_reward_rating, why: 'Overall trade quality' },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-0">
        {rows.map(r => (
          <div key={r.label} className="flex items-center justify-between gap-3 py-2
                                        border-b border-edge-light/60 dark:border-edge-dark/60 last:border-0">
            <div className="min-w-0">
              <div className="text-xs font-medium text-slate-700 dark:text-slate-200">{r.label}</div>
              <div className="text-2xs text-slate-400 dark:text-slate-500">{r.why}</div>
            </div>
            <GradeValue value={r.value} />
          </div>
        ))}
      </div>

      {(technicals.trend_explanation || technicals.volatility_explanation || technicals.risk_reward_explanation) && (
        <div className="space-y-2.5 pt-2">
          {technicals.trend_explanation && <Explainer label="Trend" text={technicals.trend_explanation} />}
          {technicals.volatility_explanation && <Explainer label="Volatility" text={technicals.volatility_explanation} />}
          {technicals.risk_reward_explanation && <Explainer label="Risk / Reward" text={technicals.risk_reward_explanation} />}
        </div>
      )}
    </div>
  )
}

function LevelsTab({ technicals, marketCap }: {
  technicals: TokenAnalysis['technicals']; marketCap: number | null
}) {
  const hasLevels = technicals.mcap_support_levels.length > 0 || technicals.mcap_resistance_levels.length > 0
  if (!hasLevels) return <p className="text-xs text-slate-500 dark:text-slate-400">No levels identified for this token.</p>

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <span className="text-xs font-semibold text-success-600 dark:text-success-400">Support</span>
          <span className="text-2xs text-slate-400 dark:text-slate-500">— market caps where buyers step in</span>
        </div>
        <div className="space-y-1">
          {technicals.mcap_support_levels.map((lvl, i) => (
            <LevelRow key={i} tier={`S${i + 1}`} value={lvl} current={marketCap} tone="up" />
          ))}
          {technicals.mcap_support_levels.length === 0 && <span className="text-2xs val-muted">None below current</span>}
        </div>
      </div>
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <span className="text-xs font-semibold text-danger-600 dark:text-danger-400">Resistance</span>
          <span className="text-2xs text-slate-400 dark:text-slate-500">— market caps that cap the move</span>
        </div>
        <div className="space-y-1">
          {technicals.mcap_resistance_levels.map((lvl, i) => (
            <LevelRow key={i} tier={`R${i + 1}`} value={lvl} current={marketCap} tone="down" />
          ))}
          {technicals.mcap_resistance_levels.length === 0 && <span className="text-2xs val-muted">None above current</span>}
        </div>
      </div>
    </div>
  )
}

function ActivityTab({ transactions, volume, overview, technicals }: {
  transactions: TokenAnalysis['transactions']
  volume: TokenAnalysis['volume']
  overview: TokenAnalysis['overview']
  technicals: TokenAnalysis['technicals']
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div>
        <h5 className="text-2xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Transactions</h5>
        <DataRow label="Buys" value={fmtNum(transactions.buys)} tone="up" />
        <DataRow label="Sells" value={fmtNum(transactions.sells)} tone="down" />
        <DataRow label="B/S Ratio" value={transactions.buy_sell_ratio?.toFixed(2) ?? '—'}
          tone={transactions.buy_sell_ratio && transactions.buy_sell_ratio >= 1.5 ? 'up'
            : transactions.buy_sell_ratio && transactions.buy_sell_ratio < 1 ? 'down' : undefined} />
        <DataRow label="Total" value={fmtNum(transactions.total_txns)} />
      </div>
      <div>
        <h5 className="text-2xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Volume</h5>
        <DataRow label="5 min" value={fmtUsd(volume.volume_5m)} />
        <DataRow label="1 hour" value={fmtUsd(volume.volume_1h)} />
        <DataRow label="6 hours" value={fmtUsd(volume.volume_6h)} />
        <DataRow label="24 hours" value={fmtUsd(volume.volume_24h)} />
      </div>
      <div>
        <h5 className="text-2xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Metadata</h5>
        <DataRow label="Age" value={fmtAge(technicals.age_hours)} />
        <DataRow label="FDV" value={fmtUsd(overview.fdv)} />
        <DataRow label="Socials" value={`${technicals.social_count} / 3`}
          tone={technicals.social_count === 3 ? 'up' : technicals.social_count === 0 ? 'down' : undefined} />
        <div className="flex items-center gap-2 pt-2">
          {overview.website && <SocialLink href={overview.website} label="Website" />}
          {overview.twitter && <SocialLink href={`https://twitter.com/${overview.twitter}`} label="Twitter" />}
          {overview.telegram && <SocialLink href={`https://t.me/${overview.telegram}`} label="Telegram" />}
        </div>
      </div>
    </div>
  )
}

// ─── Small pieces ──────────────────────────────────────────

const GRADE_TONES: Record<string, string> = {
  excellent: 'badge-success', good: 'badge-success', very_high: 'badge-success',
  strong: 'badge-success', bullish: 'badge-success', uptrend: 'badge-success',
  high: 'badge-brand', moderate: 'badge-brand', established: 'badge-brand',
  fair: 'badge-warning', new: 'badge-warning', sideways: 'badge-neutral', neutral: 'badge-neutral',
  weak: 'badge-warning', low: 'badge-warning', mature: 'badge-neutral',
  poor: 'badge-danger', danger: 'badge-danger', selling: 'badge-danger',
  bearish: 'badge-danger', downtrend: 'badge-danger', very_new: 'badge-danger', extreme: 'badge-danger',
}

function GradeValue({ value }: { value: string | null }) {
  if (!value) return <span className="text-2xs val-muted">—</span>
  return (
    <span className={`badge ${GRADE_TONES[value] ?? 'badge-neutral'} shrink-0`}>
      {value.replace(/_/g, ' ')}
    </span>
  )
}

function Explainer({ label, text }: { label: string; text: string }) {
  return (
    <div className="rounded-md bg-surface-subtle dark:bg-surface-dark-base px-3 py-2.5">
      <div className="text-2xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">{label}</div>
      <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">{text}</p>
    </div>
  )
}

function LevelRow({ tier, value, current, tone }: {
  tier: string; value: number; current: number | null; tone: 'up' | 'down'
}) {
  const pct = current ? ((value - current) / current) * 100 : null
  return (
    <div className="flex items-center justify-between gap-3 px-2.5 py-1.5 rounded
                    bg-surface-subtle dark:bg-surface-dark-base">
      <span className="text-2xs font-mono text-slate-400 dark:text-slate-500 w-6">{tier}</span>
      <span className={`text-xs font-mono tabular font-medium ${tone === 'up' ? 'val-up' : 'val-down'}`}>
        {fmtUsd(value)}
      </span>
      <span className="text-2xs val-muted tabular">
        {pct !== null ? `${pct > 0 ? '+' : ''}${pct.toFixed(0)}%` : ''}
      </span>
    </div>
  )
}

function DataRow({ label, value, tone }: { label: string; value: string; tone?: 'up' | 'down' }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-edge-light/50 dark:border-edge-dark/50 last:border-0">
      <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
      <span className={`text-xs font-mono tabular font-medium
        ${tone === 'up' ? 'val-up' : tone === 'down' ? 'val-down' : 'text-slate-700 dark:text-slate-200'}`}>
        {value}
      </span>
    </div>
  )
}

function SocialLink({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
      className="inline-flex items-center gap-1 px-2 h-6 rounded text-2xs font-medium
                 bg-surface-muted dark:bg-surface-dark-overlay
                 text-slate-600 dark:text-slate-300
                 hover:text-brand-600 dark:hover:text-brand-400 transition-colors">
      {label} <Icons.ExternalLink size={10} />
    </a>
  )
}
