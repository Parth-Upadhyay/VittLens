export interface User {
  id: number;
  email: str;
  name?: string;
  avatar_url?: string;
  provider: string;
  purpose_of_visit?: string;
}

export interface GuestSession {
  provider: 'guest';
  purpose_of_visit?: string;
  queries_used?: number;
  queries_remaining?: number;
}

export interface StockQuote {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  market_cap: number;
  fifty_two_week_low?: number;
  fifty_two_week_high?: number;
}

export interface HistoricalBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface HistoricalData {
  symbol: string;
  period: string;
  interval: string;
  series: HistoricalBar[];
}

export interface CompanyInfo {
  symbol: string;
  name: string;
  sector?: string;
  industry?: string;
  description?: string;
  website?: string;
}

export interface ProfitabilityRatios {
  roe?: number;
  roa?: number;
  roce?: number;
  net_profit_margin?: number;
  gross_margin?: number;
}

export interface ValuationRatios {
  pe_ratio?: number;
  forward_pe?: number;
  pb_ratio?: number;
  peg_ratio?: number;
}

export interface LeverageRatios {
  debt_to_equity?: number;
  current_ratio?: number;
}

export interface RatioSnapshot {
  symbol: string;
  profitability: ProfitabilityRatios;
  valuation: ValuationRatios;
  leverage: LeverageRatios;
  dividend: { dividend_yield?: number };
}

export interface KeyStatistics {
  canonical_symbol?: string;
  pe_ratio?: number;
  forward_pe?: number;
  peg_ratio?: number;
  eps?: number;
  beta?: number;
  dividend_yield?: number;
  roe?: number;
  roce?: number;
  pb_ratio?: number;
  profit_margins?: number;
  gross_margins?: number;
  revenue?: number;
  ebitda?: number;
  debt_to_equity?: number;
  current_ratio?: number;
  target_price?: number;
}

export interface CompanyDetail {
  symbol: string;
  profile?: CompanyInfo;
  quote?: StockQuote;
  quant_snapshot?: RatioSnapshot;
  key_stats?: KeyStatistics;
}

export interface NewsArticle {
  id: number;
  symbol?: string;
  canonical_symbol: string;
  headline: string;
  summary: string;
  url: string;
  source: string;
  topic_tags?: string[];
  importance_score?: number;
  sentiment_label?: string;
  published_time: string;
}

export interface FilingChunk {
  filing_id: string;
  text: string;
  source_url?: string;
  page_number?: number;
  confidence_score: number;
  symbol?: string;
}

export interface ChatRequest {
  question: string;
  symbols?: string[];
  chat_id?: string;
}

export interface ChatResponse {
  chat_id: string;
  answer: string;
  sources: string[];
  agents_used: string[];
  images: string[];
  symbols_queried: string[];
  context_truncated: boolean;
  queries_remaining?: number;
  guest_prompt_message?: string;
}

export interface ChatThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  images?: string[];
  sources?: string[];
  agents_used?: string[];
  symbols_queried?: string[];
  context_truncated?: boolean;
  created_at: string;
}

export interface PortfolioHolding {
  id: number;
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_percent: number;
  buy_date?: string;
  created_at: string;
}

export interface PortfolioSummary {
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_percent: number;
  holdings: PortfolioHolding[];
}

export interface UserPreferences {
  answer_style: 'Concise' | 'Detailed' | 'Beginner' | 'Expert';
  default_symbols: string[];
  theme: 'Dark' | 'Light' | 'System';
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  quote?: StockQuote;
  created_at: string;
}

export interface HoldingAnalysis {
  symbol: string;
  name: string;
  asset_type: 'stock' | 'etf' | 'mf';
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  total_invested: number;
  current_value: number;
  pnl: number;
  pnl_percent: number;
  day_change: number;
  weight_percent: number;
  sector: string;
  pe_ratio?: number;
  debt_to_equity?: number;
  news_summary?: string;
}

export interface PortfolioMetrics {
  total_value: number;
  total_invested: number;
  total_pnl: number;
  total_pnl_percent: number;
  day_pnl: number;
  risk_score: number;
  concentration_risk_percent: number;
}

export interface AllocationBreakdown {
  sector_breakdown: Record<string, number>;
  asset_type_breakdown: Record<string, number>;
}

export interface BenchmarkComparison {
  period: string;
  portfolio_return_percent: number;
  nifty50_return_percent: number;
  outperformance_percent: number;
}

export interface TaxLossHarvestingAlert {
  symbol: string;
  name: string;
  unrealized_loss: number;
  unrealized_loss_percent: number;
  est_stcg_tax_saving: number;
  est_ltcg_tax_saving: number;
  recommendation: string;
}

export interface PortfolioAnalysisResponse {
  id?: number;
  summary: string;
  holdings: HoldingAnalysis[];
  portfolio_metrics: PortfolioMetrics;
  allocation: AllocationBreakdown;
  rebalancing_suggestions: string[];
  news_alerts: Record<string, string[]>;
  red_flags: string[];
  benchmark_comparison?: BenchmarkComparison[];
  tax_loss_harvesting?: TaxLossHarvestingAlert[];
  images: string[];
  created_at?: string;
}

export type str = string;
