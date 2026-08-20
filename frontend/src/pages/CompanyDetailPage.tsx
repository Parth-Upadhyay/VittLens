import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CompanyService, MarketService, NewsService } from '../services/api';
import { CompanyDetail, HistoricalData, NewsArticle, KeyStatistics } from '../types';
import { MetricCard } from '../components/common/MetricCard';
import { ArrowLeft, ExternalLink, Microscope, Triangle } from 'lucide-react';
import { LineChart as ReLineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { LoadingSpinner } from '../components/common/LoadingSpinner';

export const CompanyDetailPage: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const targetSymbol = (symbol || 'RELIANCE').toUpperCase();

  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [chartData, setChartData] = useState<HistoricalData | null>(null);
  const [newsList, setNewsList] = useState<NewsArticle[]>([]);
  const [period, setPeriod] = useState('1mo');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadCompany = async () => {
      setIsLoading(true);
      try {
        const [dResult, cResult, nResult] = await Promise.allSettled([
          CompanyService.getDetail(targetSymbol),
          MarketService.getChart(targetSymbol, period),
          NewsService.getNews(targetSymbol, 10),
        ]);

        if (dResult.status === 'fulfilled') {
          setDetail(dResult.value);
        } else {
          setDetail({
            symbol: targetSymbol,
            profile: { name: targetSymbol, sector: 'Unavailable', industry: 'Unavailable' },
            quote: { symbol: targetSymbol, canonical_symbol: targetSymbol, price: 0, change: 0, change_percent: 0, volume: 0, currency: 'INR' },
            quant_snapshot: null
          } as any);
        }

        if (cResult.status === 'fulfilled') setChartData(cResult.value);
        else setChartData(null);

        if (nResult.status === 'fulfilled') setNewsList(nResult.value);
        else setNewsList([]);
      } catch (e) {
        console.error('Unexpected error loading company detail:', e);
      } finally {
        setIsLoading(false);
      }
    };
    loadCompany();
  }, [targetSymbol, period]);

  if (isLoading || !detail) {
    return <LoadingSpinner message={`Loading ${targetSymbol} details...`} className="bg-bg-primary h-full" />;
  }

  const quote = detail.quote;
  const quant = detail.quant_snapshot;
  const ks: KeyStatistics | undefined = detail.key_stats;

  // Helper: get a formatted percent from key_stats or quant_snapshot fallback
  const getPct = (ksVal?: number, quantVal?: number): string => {
    const raw = ksVal ?? quantVal;
    if (raw == null) return 'N/A';
    // Already a percentage if > 1 (e.g. 45.88 = 45.88%), otherwise multiply by 100
    const pct = Math.abs(raw) <= 1.5 ? raw * 100 : raw;
    return `${pct.toFixed(2)}%`;
  };

  const getNum = (ksVal?: number, quantVal?: number): string => {
    const raw = ksVal ?? quantVal;
    return raw != null ? raw.toFixed(2) : 'N/A';
  };

  const getDivYield = (): string => {
    let y = ks?.dividend_yield ?? quant?.dividend?.dividend_yield;
    if (y == null) return 'N/A';
    if (Math.abs(y) > 1.0) y = y / 100.0;
    if (Math.abs(y) > 1.0) y = y / 100.0;
    if (Math.abs(y) > 0.5) return 'N/A';
    return `${(y * 100).toFixed(2)}%`;
  };

  // Show metrics section if we have either source
  const hasMetrics = ks || quant;

  return (
    <div className="flex-1 p-4 md:p-8 w-full max-w-[1400px] mx-auto space-y-6 md:space-y-8 font-sans bg-bg-primary overflow-y-auto animate-page-in">

      {/* Back + Header */}
      <div className="space-y-4 pb-4 border-b border-border">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center space-x-1.5 text-sm font-medium text-tx-secondary hover:text-tx-primary nav-transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </button>

        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl md:text-3xl font-heading font-semibold text-tx-primary tracking-tight break-words">{detail.profile?.name || targetSymbol}</h1>
              <span className="font-mono text-xs text-accent bg-accent-light border border-accent/20 px-2 py-0.5 rounded flex-shrink-0">${targetSymbol}</span>
            </div>
            <div className="text-sm text-tx-secondary mt-2 font-medium">
              Sector: {detail.profile?.sector || 'NIFTY'} • {detail.profile?.industry || 'Large-Cap'}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-5">
            {quote && quote.price > 0 ? (
              <div className="flex items-center gap-3 text-left sm:text-right sm:justify-end">
                <div>
                  <div className="text-2xl md:text-3xl font-semibold text-tx-primary font-mono tabular-nums tracking-tight">₹{quote.price.toLocaleString()}</div>
                  {quote.change != null && quote.change_percent != null && (
                    <div className={`text-sm font-mono tabular-nums font-medium flex items-center sm:justify-end gap-1.5 ${quote.change >= 0 ? 'text-semantic-green' : 'text-semantic-red'}`}>
                      <Triangle className={`w-4 h-4 drop-shadow-sm transition-colors ${quote.change >= 0 ? 'fill-current' : 'fill-current rotate-180'}`} />
                      <span>{Math.abs(quote.change).toFixed(2)} ({Math.abs(quote.change_percent).toFixed(2)}%)</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-left sm:text-right max-w-[200px] text-xs text-tx-tertiary bg-bg-tertiary px-3 py-1.5 rounded-lg border border-border">
                Stock data not available on data provider platform
              </div>
            )}
            <button
              onClick={() => navigate(`/deep-analyze?symbol=${targetSymbol}`)}
              className="flex items-center space-x-2 text-sm font-medium bg-bg-secondary border border-border hover:border-accent hover:bg-bg-hover text-tx-primary px-4 py-2.5 sm:px-5 sm:py-3 rounded-xl nav-transition btn-press shadow-sm"
            >
              <Microscope className="w-4 h-4 text-accent" />
              <span>Deep Analyze</span>
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-10 pb-16">

        {/* Section 1: Financial Ratio Metrics */}
        {hasMetrics && (
          <div className="space-y-5">
            <h2 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Financial Ratio Metrics</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
              {(() => {
                const metrics = [
                  { label: "Return on Equity (ROE)", value: getPct(ks?.roe, quant?.profitability.roe) },
                  { label: "P/E Ratio", value: getNum(ks?.pe_ratio, quant?.valuation.pe_ratio) },
                  { label: "Net Profit Margin", value: getPct(ks?.profit_margins, quant?.profitability.net_profit_margin) },
                  { label: "Debt to Equity", value: getNum(ks?.debt_to_equity, quant?.leverage.debt_to_equity) },
                  { label: "Return on Capital (ROCE)", value: getPct(ks?.roce, quant?.profitability.roce) },
                  { label: "Price to Book (P/B)", value: getNum(ks?.pb_ratio, quant?.valuation.pb_ratio) },
                  { label: "Dividend Yield", value: getDivYield() },
                  { label: "PEG Ratio", value: getNum(ks?.peg_ratio, quant?.valuation.peg_ratio) },
                ].filter(m => m.value !== "N/A");

                if (metrics.length === 0) return <div className="text-xs text-tx-tertiary">No financial ratio metrics available.</div>;

                return metrics.map((m, idx) => (
                  <MetricCard key={idx} label={m.label} value={m.value} />
                ));
              })()}
            </div>
          </div>
        )}

        {/* Section 2: Price Chart */}
        {chartData && chartData.series && chartData.series.length > 0 && (
          <div className="surface-card p-6 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <h2 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Historical Price Trend</h2>
              <div className="flex space-x-1.5 p-1 bg-bg-tertiary rounded-lg border border-border">
                {['1mo', '3mo', '1y'].map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium nav-transition ${
                      period === p ? 'bg-bg-secondary text-tx-primary shadow-sm border border-border' : 'text-tx-secondary hover:text-tx-primary'
                    }`}
                  >
                    {p.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="h-96 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ReLineChart data={chartData.series}>
                  <XAxis dataKey="timestamp" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} tickMargin={10} />
                  <YAxis stroke="var(--text-tertiary)" fontSize={11} domain={['auto', 'auto']} tickLine={false} tickMargin={10} />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', borderRadius: '8px', fontSize: '13px', color: 'var(--text-primary)' }} />
                  <Line type="monotone" dataKey="close" stroke="var(--accent)" strokeWidth={2.5} dot={false} activeDot={{ r: 6, fill: 'var(--accent)' }} />
                </ReLineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Section 3: News Feed */}
        {newsList && newsList.length > 0 && (
          <div className="space-y-5">
            <h2 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Latest News</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {newsList.map((art) => (
                <div key={art.id} className="surface-card p-6 space-y-3 card-interactive flex flex-col justify-between">
                  <div className="text-xs text-tx-secondary flex items-center justify-between font-sans mb-1">
                    <div className="flex items-center space-x-2">
                      <span className="bg-accent text-white px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium">{art.source}</span>
                      <span className="font-mono text-[10px] text-accent bg-accent-light px-1.5 py-0.5 rounded border border-accent/20">${art.canonical_symbol || targetSymbol}</span>
                    </div>
                    <span className="font-mono text-[10px]">{art.published_time ? new Date(art.published_time).toLocaleDateString() : ''}</span>
                  </div>
                  <h3 className="text-[15px] font-semibold text-tx-primary leading-snug">{art.headline}</h3>
                  <p className="ai-answer-serif text-sm text-tx-secondary line-clamp-3 leading-relaxed mt-2">{art.summary}</p>
                  <div className="pt-4 mt-4 border-t border-border flex justify-end">
                    <a href={art.url} target="_blank" rel="noopener noreferrer" className="flex items-center space-x-1.5 text-xs font-medium text-accent hover:underline nav-transition">
                      <span>Read original article</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
