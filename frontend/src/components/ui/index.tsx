/**
 * Core UI primitives — single design language across the app.
 */

import { type ReactNode, useEffect, useRef, useState } from 'react'
import { Icons } from './Icon'

// ═══════════════════════════════════════════════════════════
// BUTTON
// ═══════════════════════════════════════════════════════════

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps {
  children?: ReactNode
  variant?: ButtonVariant
  size?: Size
  icon?: ReactNode
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
  className?: string
  title?: string
}

export function Button({
  children, variant = 'secondary', size = 'md',
  icon, onClick, disabled, loading, className = '', title,
}: ButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
      className={`btn btn-${size} btn-${variant} ${className}`}
    >
      {loading ? <Spinner size={size === 'sm' ? 11 : 13} /> : icon}
      {children}
    </button>
  )
}

// ═══════════════════════════════════════════════════════════
// SPINNER
// ═══════════════════════════════════════════════════════════

export function Spinner({ size = 14, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      className={`animate-spin ${className}`}
      style={{ animationDuration: '700ms' }}
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.2" />
      <path d="M12 3a9 9 0 0 1 9 9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

// ═══════════════════════════════════════════════════════════
// BADGE
// ═══════════════════════════════════════════════════════════

type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger'

export function Badge({ children, tone = 'neutral', className = '' }: {
  children: ReactNode; tone?: BadgeTone; className?: string
}) {
  return <span className={`badge badge-${tone} ${className}`}>{children}</span>
}

// ═══════════════════════════════════════════════════════════
// SEGMENTED CONTROL
// ═══════════════════════════════════════════════════════════

export function Segmented<T extends string>({ options, value, onChange, className = '' }: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  className?: string
}) {
  return (
    <div className={`segmented ${className}`} role="tablist">
      {options.map((opt) => (
        <button
          key={opt.value}
          role="tab"
          aria-selected={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={`segmented-item ${value === opt.value ? 'segmented-item-active' : ''}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// PANEL
// ═══════════════════════════════════════════════════════════

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>
}

export function PanelHeader({ title, subtitle, actions }: {
  title: string; subtitle?: string; actions?: ReactNode
}) {
  return (
    <div className="panel-header">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{title}</h3>
        {subtitle && <p className="text-2xs text-slate-500 dark:text-slate-400 truncate">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-1.5 shrink-0">{actions}</div>}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// STAT CARD
// ═══════════════════════════════════════════════════════════

export function StatCard({ label, value, delta, tone, hint }: {
  label: string
  value: string
  delta?: string
  tone?: 'up' | 'down' | 'neutral'
  hint?: string
}) {
  const valueColor =
    tone === 'up' ? 'val-up' : tone === 'down' ? 'val-down' : 'text-slate-900 dark:text-slate-100'

  return (
    <div className="surface rounded-lg px-3.5 py-3">
      <div className="flex items-center gap-1">
        <span className="text-2xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {label}
        </span>
        {hint && (
          <span title={hint} className="text-slate-400 dark:text-slate-500 cursor-help">
            <Icons.Info size={11} />
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2 mt-1">
        <span className={`text-xl font-semibold font-mono tabular ${valueColor}`}>{value}</span>
        {delta && (
          <span className={`text-2xs font-medium ${tone === 'up' ? 'val-up' : tone === 'down' ? 'val-down' : 'val-muted'}`}>
            {delta}
          </span>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// EMPTY STATE
// ═══════════════════════════════════════════════════════════

export function EmptyState({ icon, title, description, action }: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      {icon && (
        <div className="mb-3 text-slate-300 dark:text-slate-600">{icon}</div>
      )}
      <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300">{title}</h4>
      {description && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// SKELETON LOADERS
// ═══════════════════════════════════════════════════════════

export function SkeletonRow({ cols = 8 }: { cols?: number }) {
  return (
    <tr className="border-b border-edge-light/60 dark:border-edge-dark/60">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-3 h-10">
          <div className="skeleton h-3" style={{ width: i === 1 ? '70%' : '50%' }} />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonCard() {
  return (
    <div className="surface rounded-lg px-3.5 py-3">
      <div className="skeleton h-2.5 w-16 mb-2" />
      <div className="skeleton h-5 w-24" />
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// ALERT
// ═══════════════════════════════════════════════════════════

export function Alert({ tone = 'danger', children }: {
  tone?: 'danger' | 'warning' | 'info'
  children: ReactNode
}) {
  const styles = {
    danger: 'bg-danger-50 dark:bg-danger-500/8 border-danger-200 dark:border-danger-500/20 text-danger-700 dark:text-danger-300',
    warning: 'bg-warning-50 dark:bg-warning-500/8 border-warning-200 dark:border-warning-500/20 text-warning-700 dark:text-warning-300',
    info: 'bg-brand-50 dark:bg-brand-500/8 border-brand-200 dark:border-brand-500/20 text-brand-700 dark:text-brand-300',
  }
  const icon = tone === 'danger' || tone === 'warning' ? <Icons.Warning size={14} /> : <Icons.Info size={14} />

  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-md border text-xs ${styles[tone]}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// MODAL
// ═══════════════════════════════════════════════════════════

/**
 * Centered dialog with backdrop.
 *
 * Closes on Escape and backdrop click. Locks body scroll while open so the
 * page behind doesn't drift.
 */
export function Modal({ open, onClose, title, subtitle, children, footer, width = 'max-w-md' }: {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
  width?: string
}) {
  useEffect(() => {
    if (!open) return
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onEsc)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onEsc)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4
                 bg-slate-900/40 dark:bg-black/60 backdrop-blur-[2px] animate-fade-in"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={e => e.stopPropagation()}
        className={`w-full ${width} rounded-lg overflow-hidden animate-slide-down
                    border border-edge-light dark:border-edge-dark
                    bg-surface-base dark:bg-surface-dark-raised
                    shadow-xl dark:shadow-dark-lg`}
      >
        <div className="flex items-start justify-between gap-3 px-4 py-3
                        border-b border-edge-light dark:border-edge-dark">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{title}</h3>
            {subtitle && (
              <p className="text-2xs text-slate-500 dark:text-slate-400 truncate">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            title="Close"
            className="shrink-0 p-1 rounded text-slate-400 hover:text-slate-700
                       dark:hover:text-slate-200 transition-colors"
          >
            <Icons.X size={14} />
          </button>
        </div>

        <div className="px-4 py-3">{children}</div>

        {footer && (
          <div className="px-4 py-2.5 border-t border-edge-light dark:border-edge-dark
                          bg-surface-subtle dark:bg-surface-dark-base">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// FORMATTERS (shared)
// ═══════════════════════════════════════════════════════════

export function fmtUsd(v: number | null | undefined, compact = true): string {
  if (v == null) return '—'
  if (!compact) return `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
  const abs = Math.abs(v)
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}K`
  return `$${v.toFixed(0)}`
}

export function fmtPrice(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v === 0) return '$0'
  if (v < 0.00001) return `$${v.toExponential(2)}`
  if (v < 1) return `$${v.toPrecision(4)}`
  if (v < 1000) return `$${v.toFixed(3)}`
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

export function fmtNum(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`
  return v.toLocaleString('en-US')
}

export function fmtPct(v: number | null | undefined): { text: string; tone: 'up' | 'down' | 'neutral' } {
  if (v == null) return { text: '—', tone: 'neutral' }
  const abs = Math.abs(v)
  const text = abs >= 10000
    ? `${v > 0 ? '+' : '-'}${(abs / 1000).toFixed(0)}K%`
    : `${v >= 0 ? '+' : ''}${v.toFixed(abs < 10 ? 2 : 1)}%`
  return { text, tone: v > 0 ? 'up' : v < 0 ? 'down' : 'neutral' }
}

/**
 * Chain aliases -> DexScreener chain ids.
 *
 * GMGN reports "sol"/"eth", which DexScreener rejects: a link built with the
 * short slug renders "no pair found". The backend normalizes these now, but
 * links are also built from cached and stored data, so normalize here too.
 */
const CHAIN_ALIASES: Record<string, string> = {
  sol: 'solana',
  eth: 'ethereum',
  bnb: 'bsc',
  binance: 'bsc',
}

/** Build a DexScreener link with a chain id DexScreener actually accepts. */
export function dexUrl(chain: string, address: string, params = ''): string {
  const id = CHAIN_ALIASES[chain?.toLowerCase()] ?? chain
  return `https://dexscreener.com/${id}/${address}${params}`
}

/** Max ticker length before truncation — keeps table columns from stretching. */
export const TICKER_MAX = 10

export function fmtSymbol(symbol: string | null | undefined, max = TICKER_MAX): string {
  if (!symbol) return '—'
  return symbol.length > max ? `${symbol.slice(0, max)}…` : symbol
}

export function fmtAge(hours: number | null | undefined): string {
  if (hours == null) return '—'
  if (hours < 1) return `${Math.round(hours * 60)}m`
  if (hours < 48) return `${Math.round(hours)}h`
  const days = hours / 24
  if (days < 30) return `${days.toFixed(days < 10 ? 1 : 0)}d`
  return `${(days / 30).toFixed(1)}mo`
}

// ═══════════════════════════════════════════════════════════
// DROPDOWN (used for column visibility)
// ═══════════════════════════════════════════════════════════

export function Dropdown({ trigger, children, align = 'right' }: {
  trigger: ReactNode
  children: ReactNode
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen(o => !o)}>{trigger}</div>
      {open && (
        <div className={`absolute top-full mt-1 z-50 min-w-[180px] py-1
                        rounded-md border border-edge-light dark:border-edge-dark
                        bg-surface-base dark:bg-surface-dark-overlay
                        shadow-lg dark:shadow-dark-lg
                        animate-slide-down
                        ${align === 'right' ? 'right-0' : 'left-0'}`}>
          {children}
        </div>
      )}
    </div>
  )
}

export function DropdownItem({ children, onClick, checked }: {
  children: ReactNode; onClick?: () => void; checked?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2 px-2.5 h-7 text-xs text-left
                 text-slate-700 dark:text-slate-200
                 hover:bg-surface-muted dark:hover:bg-surface-dark-hover
                 transition-colors duration-100"
    >
      <span className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center shrink-0
                       ${checked
                         ? 'bg-brand-500 border-brand-500 text-white'
                         : 'border-slate-300 dark:border-slate-600'}`}>
        {checked && <Icons.Check size={10} />}
      </span>
      {children}
    </button>
  )
}

export function DropdownLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-2.5 py-1 text-2xs font-semibold uppercase tracking-wide
                    text-slate-400 dark:text-slate-500">
      {children}
    </div>
  )
}

export function DropdownDivider() {
  return <div className="my-1 border-t border-edge-light dark:border-edge-dark" />
}

// ═══════════════════════════════════════════════════════════
// TICKER
// ═══════════════════════════════════════════════════════════

/**
 * Token ticker, capped at TICKER_MAX characters.
 *
 * Long memecoin tickers otherwise blow out column widths. The untruncated
 * value stays available via the native tooltip.
 */
export function Ticker({ symbol, className = '' }: { symbol: string; className?: string }) {
  const shown = fmtSymbol(symbol)
  return (
    <span className={className} title={shown !== symbol ? symbol : undefined}>
      {shown}
    </span>
  )
}

// ═══════════════════════════════════════════════════════════
// WATCH STAR
// ═══════════════════════════════════════════════════════════

export function WatchStar({ active, onClick }: { active: boolean; onClick: (e: React.MouseEvent) => void }) {
  return (
    <button
      onClick={onClick}
      title={active ? 'Remove from watchlist' : 'Add to watchlist (w)'}
      className={`inline-flex items-center justify-center w-6 h-6 rounded
                  transition-all duration-150
                  ${active
                    ? 'text-warning-500'
                    : 'text-slate-300 dark:text-slate-600 opacity-0 group-hover:opacity-100 hover:text-warning-500'}`}
    >
      <svg width="14" height="14" viewBox="0 0 24 24"
        fill={active ? 'currentColor' : 'none'}
        stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="m12 3 2.6 5.6 6.1.8-4.4 4.3 1 6.1L12 17l-5.3 2.8 1-6.1L3.3 9.4l6.1-.8L12 3Z" />
      </svg>
    </button>
  )
}

// ═══════════════════════════════════════════════════════════
// KEYBOARD HINT
// ═══════════════════════════════════════════════════════════

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1
                    rounded border border-edge-light-strong dark:border-edge-dark-strong
                    bg-surface-muted dark:bg-surface-dark-base
                    text-[10px] font-mono font-medium
                    text-slate-600 dark:text-slate-400">
      {children}
    </kbd>
  )
}

export function KeyboardHints() {
  return (
    <div className="hidden xl:flex items-center gap-3 text-2xs text-slate-400 dark:text-slate-500">
      <span className="flex items-center gap-1"><Kbd>j</Kbd><Kbd>k</Kbd> navigate</span>
      <span className="flex items-center gap-1"><Kbd>↵</Kbd> open</span>
      <span className="flex items-center gap-1"><Kbd>w</Kbd> watch</span>
      <span className="flex items-center gap-1"><Kbd>/</Kbd> search</span>
    </div>
  )
}
