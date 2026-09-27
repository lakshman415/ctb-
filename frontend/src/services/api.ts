/**
 * API client for the CTB backend.
 */

import type { ScannerResult } from '../types/scanner'
import type { TokenAnalysis } from '../types/analysis'

const BASE_URL = '/api/v1'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error')
    throw new ApiError(response.status, `API error ${response.status}: ${errorText}`)
  }
  return response.json() as Promise<T>
}

// Scanner
export async function getScannerResults(): Promise<ScannerResult> {
  return request<ScannerResult>('/scanner/results')
}

export async function getAllTokens(): Promise<ScannerResult> {
  return request<ScannerResult>('/tokens/unfiltered')
}

export async function getTrendingTokens(chain: string = 'all', limit: number = 10, interval: string = '24h'): Promise<ScannerResult> {
  const params = new URLSearchParams({ chain, limit: limit.toString(), interval })
  return request<ScannerResult>(`/trending/top?${params}`)
}

export async function triggerScan(): Promise<ScannerResult> {
  return request<ScannerResult>('/scanner/trigger', { method: 'POST' })
}

// Analysis
export async function analyzeToken(chain: string, address: string): Promise<TokenAnalysis> {
  const params = new URLSearchParams({ chain, address })
  return request<TokenAnalysis>(`/analysis/token?${params}`)
}

// Wallet
export async function getWalletActivity(chain: string, limit: number = 30, wallet?: string): Promise<unknown> {
  const params = new URLSearchParams({ chain, limit: limit.toString() })
  if (wallet) params.set('wallet', wallet)
  return request<unknown>(`/wallet/activity?${params}`)
}

export async function getWalletStats(chain: string, wallet: string, period: string = '30d'): Promise<unknown> {
  const params = new URLSearchParams({ chain, wallet, period })
  return request<unknown>(`/wallet/stats?${params}`)
}

// Journal (DB-backed)
export interface JournalEntry {
  id: number
  category: string
  text: string
  tx_hash: string | null
  token_symbol: string | null
  chain: string | null
  created_at: string
}

export async function getJournalEntries(category: string = 'all'): Promise<JournalEntry[]> {
  return request<JournalEntry[]>(`/journal/entries?category=${category}`)
}

export async function createJournalEntry(entry: {
  category: string; text: string; tx_hash?: string; token_symbol?: string; chain?: string
}): Promise<JournalEntry> {
  return request<JournalEntry>('/journal/entries', {
    method: 'POST',
    body: JSON.stringify(entry),
  })
}

export async function deleteJournalEntry(id: number): Promise<void> {
  await request<unknown>(`/journal/entries/${id}`, { method: 'DELETE' })
}

export async function getTradeNotes(): Promise<Record<string, { id: number; text: string }>> {
  return request<Record<string, { id: number; text: string }>>('/journal/trade-notes')
}

// ═══════════════════════════════════════════════════════════
// WATCHLIST + ALERTS
// ═══════════════════════════════════════════════════════════

export interface AlertRule {
  id: number
  metric: string
  condition: 'above' | 'below'
  threshold: number
  enabled: boolean
  triggered: boolean
  triggered_at: string | null
  triggered_value: number | null
}

export interface WatchlistItem {
  id: number
  watchlist_id: number | null
  chain: string
  token_address: string
  pair_address: string
  symbol: string
  name: string
  added_price: number | null
  added_market_cap: number | null
  note: string | null
  position: number
  created_at: string
  alerts: AlertRule[]
}

/** A named watchlist. `position` drives the display order. */
export interface Watchlist {
  id: number
  name: string
  position: number
  created_at: string
  item_count: number
}

/** A watchlist item enriched with current market data. */
export interface WatchlistTokenQuote {
  item_id: number
  watchlist_id: number | null
  chain: string
  token_address: string
  pair_address: string
  symbol: string
  name: string
  price: number | null
  market_cap: number | null
  volume_24h: number | null
  liquidity: number | null
  age_hours: number | null
  price_change_5m: number | null
  price_change_1h: number | null
  price_change_24h: number | null
  added_price: number | null
  added_market_cap: number | null
  note: string | null
  position: number
  created_at: string
  alert_count: number
  is_stale: boolean
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  return request<WatchlistItem[]>('/watchlist/items')
}

export async function addToWatchlist(item: {
  chain: string; token_address: string; pair_address: string
  symbol: string; name: string
  watchlist_id?: number | null
  added_price?: number | null; added_market_cap?: number | null
}): Promise<WatchlistItem> {
  return request<WatchlistItem>('/watchlist/items', {
    method: 'POST',
    body: JSON.stringify(item),
  })
}

// ─── Lists ─────────────────────────────────────────────────

export async function getWatchlists(): Promise<Watchlist[]> {
  return request<Watchlist[]>('/watchlist/lists')
}

export async function createWatchlist(name: string): Promise<Watchlist> {
  return request<Watchlist>('/watchlist/lists', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export async function renameWatchlist(id: number, name: string): Promise<Watchlist> {
  return request<Watchlist>(`/watchlist/lists/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export async function deleteWatchlist(id: number): Promise<void> {
  await request<unknown>(`/watchlist/lists/${id}`, { method: 'DELETE' })
}

/** Persist a new list order. Index in `ids` becomes the stored position. */
export async function reorderWatchlists(ids: number[]): Promise<Watchlist[]> {
  return request<Watchlist[]>('/watchlist/lists/reorder', {
    method: 'PATCH',
    body: JSON.stringify({ ids }),
  })
}

export async function getWatchlistTokens(listId: number): Promise<WatchlistTokenQuote[]> {
  return request<WatchlistTokenQuote[]>(`/watchlist/lists/${listId}/tokens`)
}

export async function removeFromWatchlist(id: number): Promise<void> {
  await request<unknown>(`/watchlist/items/${id}`, { method: 'DELETE' })
}

export async function createAlert(alert: {
  watchlist_id: number; metric: string; condition: 'above' | 'below'; threshold: number
}): Promise<AlertRule> {
  return request<AlertRule>('/watchlist/alerts', {
    method: 'POST',
    body: JSON.stringify(alert),
  })
}

export async function deleteAlert(id: number): Promise<void> {
  await request<unknown>(`/watchlist/alerts/${id}`, { method: 'DELETE' })
}

export async function toggleAlert(id: number): Promise<{ enabled: boolean }> {
  return request<{ enabled: boolean }>(`/watchlist/alerts/${id}/toggle`, { method: 'PATCH' })
}

export async function acknowledgeAlert(id: number): Promise<void> {
  await request<unknown>(`/watchlist/alerts/${id}/acknowledge`, { method: 'POST' })
}

export async function getTriggeredAlerts(): Promise<AlertRule[]> {
  return request<AlertRule[]>('/watchlist/alerts/triggered')
}
