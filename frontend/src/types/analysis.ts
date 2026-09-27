/**
 * Types for the token analysis response.
 * Mirrors backend/app/schemas/analysis.py
 */

export interface TokenOverview {
  pair_address: string
  token_address: string
  name: string
  symbol: string
  chain: string
  dex: string
  price: number | null
  market_cap: number | null
  fdv: number | null
  liquidity: number | null
  pair_created_at: string | null
  website: string | null
  twitter: string | null
  telegram: string | null
  dexscreener_url: string | null
}

export interface VolumeData {
  volume_5m: number | null
  volume_1h: number | null
  volume_6h: number | null
  volume_24h: number | null
}

export interface TransactionData {
  buys: number | null
  sells: number | null
  buy_sell_ratio: number | null
  total_txns: number | null
}

export interface PriceChangeData {
  change_5m: number | null
  change_1h: number | null
  change_6h: number | null
  change_24h: number | null
}

export interface TechnicalIndicators {
  momentum_1h: string | null
  momentum_24h: string | null
  liquidity_mcap_ratio: number | null
  liquidity_grade: string | null
  volume_to_liquidity_ratio: number | null
  volume_grade: string | null
  buy_pressure_grade: string | null
  age_hours: number | null
  age_grade: string | null
  social_count: number
  support_levels: number[]
  resistance_levels: number[]
  mcap_support_levels: number[]
  mcap_resistance_levels: number[]
  trend_direction: string | null
  trend_strength: string | null
  trend_explanation: string | null
  volatility_grade: string | null
  volatility_explanation: string | null
  risk_reward_rating: string | null
  risk_reward_explanation: string | null
  key_signals: string[]
  overall_grade: string | null
  risk_level: string | null
  summary: string[]
}

export interface TokenAnalysis {
  overview: TokenOverview
  volume: VolumeData
  transactions: TransactionData
  price_changes: PriceChangeData
  technicals: TechnicalIndicators
  score: number
  analyzed_at: string
}
