import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Microscope, Search, ChevronDown, ChevronUp } from 'lucide-react';
import { MarketService } from '../services/api';
import { SymbolSearch } from '../components/common/SymbolSearch';

// Human-readable labels for yfinance info keys
const DEEP_STAT_LABELS: Record<string, string> = {
  currentPrice: 'Current Price',
  previousClose: 'Previous Close',
  open: 'Open',
  dayHigh: 'Day High',
  dayLow: 'Day Low',
  volume: 'Volume',
  averageVolume: 'Avg Volume (3M)',
  marketCap: 'Market Cap',
  enterpriseValue: 'Enterprise Value',
  trailingPE: 'P/E Ratio (TTM)',
  forwardPE: 'Forward P/E',
  priceToBook: 'Price to Book',
  priceToSalesTrailing12Months: 'Price to Sales',
  enterpriseToRevenue: 'EV / Revenue',
  enterpriseToEbitda: 'EV / EBITDA',
  trailingEps: 'EPS (TTM)',
  forwardEps: 'Forward EPS',
  pegRatio: 'PEG Ratio',
  bookValue: 'Book Value Per Share',
  dividendRate: 'Dividend Rate (₹)',
  dividendYield: 'Dividend Yield',
  payoutRatio: 'Payout Ratio',
  fiveYearAvgDividendYield: '5Y Avg Dividend Yield',
  beta: 'Beta',
  returnOnEquity: 'Return on Equity',
  returnOnCapitalEmployed: 'Return on Capital Employed',
  profitMargins: 'Net Profit Margin',
  grossMargins: 'Gross Margin',
  operatingMargins: 'Operating Margin',
  ebitdaMargins: 'EBITDA Margin',
  totalRevenue: 'Total Revenue',
  revenuePerShare: 'Revenue Per Share',
  revenueGrowth: 'Revenue Growth (YoY)',
  earningsGrowth: 'Earnings Growth (YoY)',
  earningsQuarterlyGrowth: 'Quarterly Earnings Growth',
  ebitda: 'EBITDA',
  totalDebt: 'Total Debt',
  totalCash: 'Total Cash',
  totalCashPerShare: 'Cash Per Share',
  debtToEquity: 'Debt to Equity',
  currentRatio: 'Current Ratio',
  quickRatio: 'Quick Ratio',
  sharesOutstanding: 'Shares Outstanding',
  floatShares: 'Float Shares',
  heldPercentInsiders: 'Insider Holding %',
  heldPercentInstitutions: 'Institutional Holding %',
  fiftyTwoWeekHigh: '52W High',
  fiftyTwoWeekLow: '52W Low',
  fiftyDayAverage: '50D Avg Price',
  twoHundredDayAverage: '200D Avg Price',
  targetMeanPrice: 'Analyst Target (Mean)',
  targetHighPrice: 'Analyst Target (High)',
  targetLowPrice: 'Analyst Target (Low)',
  recommendationKey: 'Analyst Recommendation',
  numberOfAnalystOpinions: 'Analyst Coverage Count',
  sector: 'Sector',
  industry: 'Industry',
  country: 'Country',
  fullTimeEmployees: 'Full-Time Employees',
  website: 'Website',
  trailingPegRatio: 'Trailing PEG Ratio',
  longName: 'Company Name',
  shortName: 'Short Name',
  currency: 'Currency',
  exchange: 'Exchange',
  quoteType: 'Quote Type',
  regularMarketPrice: 'Regular Market Price',
};

const DEEP_STAT_GROUPS: { label: string; keys: string[] }[] = [
  {
    label: 'Company Info',
    keys: ['longName', 'shortName', 'sector', 'industry', 'country', 'fullTimeEmployees', 'website', 'currency', 'exchange'],
  },
  {
    label: 'Price & Trading',
    keys: ['currentPrice', 'regularMarketPrice', 'previousClose', 'open', 'dayHigh', 'dayLow', 'volume', 'averageVolume', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'fiftyDayAverage', 'twoHundredDayAverage', 'beta'],
  },
  {
    label: 'Valuation',
    keys: ['marketCap', 'enterpriseValue', 'trailingPE', 'forwardPE', 'priceToBook', 'priceToSalesTrailing12Months', 'enterpriseToRevenue', 'enterpriseToEbitda', 'pegRatio', 'trailingPegRatio', 'bookValue'],
  },
  {
    label: 'Profitability & Returns',
    keys: ['profitMargins', 'grossMargins', 'operatingMargins', 'ebitdaMargins', 'returnOnEquity', 'returnOnCapitalEmployed', 'earningsGrowth', 'revenueGrowth', 'earningsQuarterlyGrowth'],
  },
  {
    label: 'Income & EPS',
    keys: ['totalRevenue', 'revenuePerShare', 'ebitda', 'trailingEps', 'forwardEps'],
  },
  {
    label: 'Balance Sheet & Liquidity',
    keys: ['totalDebt', 'totalCash', 'totalCashPerShare', 'debtToEquity', 'currentRatio', 'quickRatio'],
  },
  {
    label: 'Dividends',
    keys: ['dividendRate', 'dividendYield', 'payoutRatio', 'fiveYearAvgDividendYield'],
  },
  {
    label: 'Ownership & Shares',
    keys: ['sharesOutstanding', 'floatShares', 'heldPercentInsiders', 'heldPercentInstitutions'],
  },
  {
    label: 'Analyst Targets',
    keys: ['targetMeanPrice', 'targetHighPrice', 'targetLowPrice', 'recommendationKey', 'numberOfAnalystOpinions'],
  },
];

function formatDeepValue(key: string, val: any): string {
  if (val === null || val === undefined) return 'N/A';
  if (typeof val === 'string') return val;
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';

  const percentKeys = ['profitMargins', 'grossMargins', 'operatingMargins', 'ebitdaMargins', 'returnOnEquity',
    'returnOnCapitalEmployed', 'dividendYield', 'payoutRatio', 'fiveYearAvgDividendYield',
    'heldPercentInsiders', 'heldPercentInstitutions', 'revenueGrowth', 'earningsGrowth', 'earningsQuarterlyGrowth'];
  const largeNumKeys = ['marketCap', 'enterpriseValue', 'totalRevenue', 'ebitda', 'totalDebt', 'totalCash',
    'sharesOutstanding', 'floatShares', 'volume', 'averageVolume'];
  const priceKeys = ['currentPrice', 'regularMarketPrice', 'previousClose', 'open', 'dayHigh', 'dayLow',
    'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'fiftyDayAverage', 'twoHundredDayAverage',
    'targetMeanPrice', 'targetHighPrice', 'targetLowPrice', 'bookValue', 'totalCashPerShare',
    'revenuePerShare', 'dividendRate', 'trailingEps', 'forwardEps'];

  if (percentKeys.includes(key)) {
    let num = typeof val === 'number' ? val : parseFloat(val);
    if (!isNaN(num)) {
      if (Math.abs(num) > 1.0) num = num / 100.0;
      if (Math.abs(num) > 1.0) num = num / 100.0;
      if (Math.abs(num) > 0.5) return 'N/A';
      return `${(num * 100).toFixed(2)}%`;
    }
  }
  if (largeNumKeys.includes(key)) {
    if (val >= 1e12) return `₹${(val / 1e12).toFixed(2)}T`;
    if (val >= 1e9) return `₹${(val / 1e9).toFixed(2)}B`;
    if (val >= 1e6) return `₹${(val / 1e6).toFixed(2)}M`;
    if (val >= 1e3) return `₹${(val / 1e3).toFixed(2)}K`;
    return `₹${val.toLocaleString()}`;
  }
  if (priceKeys.includes(key)) return `₹${typeof val === 'number' ? val.toLocaleString(undefined, { maximumFractionDigits: 2 }) : val}`;
  if (typeof val === 'number') return val.toLocaleString(undefined, { maximumFractionDigits: 4 });
  return String(val);
}

export const DeepAnalyzePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [selectedSymbol, setSelectedSymbol] = useState(searchParams.get('symbol') || '');
  const [deepData, setDeepData] = useState<Record<string, any> | null>(null);
  const [ticker, setTicker] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  const runAnalysis = async (sym: string) => {
    if (!sym) return;
    setIsLoading(true);
    setDeepData(null);
    setError(null);
    try {
      const result = await MarketService.deepAnalyze(sym);
      setDeepData(result.data);
      setTicker(result.ticker);
      const expanded: Record<string, boolean> = {};
      DEEP_STAT_GROUPS.forEach(g => { expanded[g.label] = true; });
      setExpandedGroups(expanded);
    } catch {
      setError('Could not fetch data. This company may not have active data on Yahoo Finance.');
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-trigger if navigated from company page with ?symbol=
  useEffect(() => {
    const sym = searchParams.get('symbol');
    if (sym) {
      setSelectedSymbol(sym);
      runAnalysis(sym);
    }
  }, []);

  const handleAnalyze = () => runAnalysis(selectedSymbol);

  const toggleGroup = (label: string) => {
    setExpandedGroups(prev => ({ ...prev, [label]: !prev[label] }));
  };

  const totalMetrics = deepData
    ? DEEP_STAT_GROUPS.flatMap(g => g.keys).filter(k => deepData[k] !== undefined).length
    : 0;

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">

      {/* Header */}
      <div className="flex items-center space-x-3 pb-2">
        <div className="w-9 h-9 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
          <Microscope className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-medium text-cream tracking-tight">Deep Analyze</h1>
          <p className="text-xs text-cream-muted">All available Yahoo Finance metrics for any company — in one view</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm">
        <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Select Company</h2>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <SymbolSearch
              onSelect={setSelectedSymbol}
              placeholder="Search any listed company..."
              clearOnSelect={false}
            />
          </div>
          <button
            onClick={handleAnalyze}
            disabled={!selectedSymbol || isLoading}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-cream text-xs font-medium px-5 py-2 rounded-lg flex items-center space-x-2 shadow-sm transition-colors whitespace-nowrap"
          >
            <Search className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Fetching...' : 'Run Analysis'}</span>
          </button>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex flex-col items-center py-16 space-y-3">
          <Microscope className="w-8 h-8 text-accent animate-pulse" />
          <div className="text-xs text-cream-muted">Fetching all available data from Yahoo Finance...</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-[#1A0A0A] border border-semantic-red/30 rounded-xl p-4 text-xs text-semantic-red text-center">
          {error}
        </div>
      )}

      {/* Results */}
      {deepData && (
        <div className="space-y-4">
          {/* Summary Bar */}
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-cream">{deepData.longName || selectedSymbol}</span>
              <span className="ml-2 font-mono text-xs text-accent bg-[#0D1912] border border-hairline px-2 py-0.5 rounded">{ticker}</span>
            </div>
            <span className="text-xs text-cream-muted tabular-nums">{totalMetrics} metrics found</span>
          </div>

          {/* Groups */}
          <div className="space-y-2">
            {DEEP_STAT_GROUPS.map((group) => {
              const groupData = group.keys
                .filter(k => deepData[k] !== undefined && deepData[k] !== null)
                .map(k => ({ key: k, label: DEEP_STAT_LABELS[k] || k, value: deepData[k] }));

              if (groupData.length === 0) return null;
              const isOpen = expandedGroups[group.label] !== false;

              return (
                <div key={group.label} className="bg-[#0D1912] border border-hairline rounded-xl overflow-hidden shadow-sm">
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#14251B]/50 transition-colors"
                  >
                    <div className="flex items-center space-x-2.5">
                      <span className="text-xs font-medium text-cream uppercase tracking-wider">{group.label}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] text-cream-muted tabular-nums">{groupData.length} metrics</span>
                      {isOpen
                        ? <ChevronUp className="w-3.5 h-3.5 text-cream-muted" />
                        : <ChevronDown className="w-3.5 h-3.5 text-cream-muted" />
                      }
                    </div>
                  </button>

                  {isOpen && (
                    <div className="border-t border-hairline">
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-px bg-hairline">
                        {groupData.map(({ key, label, value }) => (
                          <div key={key} className="bg-[#0D1912] px-4 py-3 space-y-1 hover:bg-[#14251B]/30 transition-colors">
                            <div className="text-[10px] text-cream-muted uppercase tracking-wide leading-tight">{label}</div>
                            <div className="text-xs font-mono font-medium text-cream tabular-nums break-all">
                              {formatDeepValue(key, value)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!deepData && !isLoading && !error && (
        <div className="flex flex-col items-center py-20 space-y-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent/5 border border-accent/10 flex items-center justify-center">
            <Microscope className="w-8 h-8 text-accent/40" />
          </div>
          <div>
            <div className="text-sm font-medium text-cream-muted">Search a company above</div>
            <div className="text-xs text-cream-dim mt-1">We'll pull every available metric from Yahoo Finance — P/E, ROE, ROCE, P/B, margins, analyst targets, and more</div>
          </div>
        </div>
      )}
    </div>
  );
};
