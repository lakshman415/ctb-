/**
 * TypeScript types matching the backend API response schemas.
 *
 * These mirror backend/app/schemas/scanner.py exactly.
 */

export interface RankedToken {
  rank: number
  score: number
  score_reasons: string[]
  category: string
  chain: string
  name: string
  symbol: string
  pair_address: string
  token_address: string
  price: number | null
  market_cap: number | null
  liquidity: number | null
  volume_24h: number | null
  buys: number | null
  sells: number | null
  buy_sell_ratio: number | null
  price_change_5m: number | null
  price_change_1h: number | null
  price_change_24h: number | null
  liquidity_mcap_ratio: number | null
}

export interface ScannerResult {
  scanned_at: string
  total_pairs_fetched: number
  total_after_filter: number
  tokens: RankedToken[]
}

export type CategoryFilter = 'all' | 'early' | 'mid' | 'large'
