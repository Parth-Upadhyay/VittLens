import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CompanyService, MarketService, NewsService } from '../services/api';
import { CompanyDetail, HistoricalData, NewsArticle } from '../types';
import { MetricCard } from '../components/common/MetricCard';
import { ArrowLeft, ExternalLink, Microscope } from 'lucide-react';
import { LineChart as ReLineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

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
    return <div className="p-12 text-center text-xs text-cream-muted font-sans bg-[#060E0A]">Loading {targetSymbol} details...</div>;
  }

  const quote = detail.quote;
  const quant = detail.quant_snapshot;

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">

      {/* Back + Header */}
      <div className="space-y-3 pb-2">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center space-x-1 text-xs text-cream-muted hover:text-cream transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-2xl font-medium text-cream">{detail.profile?.name || targetSymbol}</h1>
              <span className="font-mono text-xs text-accent bg-[#0D1912] border border-hairline px-2 py-0.5 rounded tabular-nums">${targetSymbol}</span>
            </div>
            <div className="text-xs text-cream-muted mt-1">
              Sector: {detail.profile?.sector || 'NIFTY'} • {detail.profile?.industry || 'Large-Cap'}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {quote && (
              <div className="text-right">
                <div className="text-2xl font-medium text-cream font-mono tabular-nums">₹{quote.price.toLocaleString()}</div>
                <div className={`text-xs font-mono tabular-nums ${quote.change >= 0 ? 'text-semantic-green' : 'text-semantic-red'}`}>
                  {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)} ({quote.change_percent.toFixed(2)}%)
                </div>
              </div>
            )}
            <button
              onClick={() => navigate(`/deep-analyze?symbol=${targetSymbol}`)}
              className="flex items-center space-x-1.5 text-xs bg-[#0D1912] border border-hairline hover:border-accent/40 text-cream-muted hover:text-cream px-3 py-2 rounded-lg transition-colors"
            >
              <Microscope className="w-3.5 h-3.5 text-accent" />
              <span>Deep Analyze</span>
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-8 pb-12">

        {/* Section 1: Financial Ratio Metrics */}
        {quant && (
          <div className="space-y-4">
            <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Financial Ratio Metrics</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <MetricCard label="Return on Equity (ROE)" value={quant.profitability.roe != null ? `${(quant.profitability.roe * 100).toFixed(2)}%` : 'N/A'} />
              <MetricCard label="P/E Ratio" value={quant.valuation.pe_ratio != null ? quant.valuation.pe_ratio.toFixed(2) : 'N/A'} />
              <MetricCard label="Net Profit Margin" value={quant.profitability.net_profit_margin != null ? `${(quant.profitability.net_profit_margin * 100).toFixed(2)}%` : 'N/A'} />
              <MetricCard label="Debt to Equity" value={quant.leverage.debt_to_equity != null ? quant.leverage.debt_to_equity.toFixed(2) : 'N/A'} />
              <MetricCard label="Return on Capital (ROCE)" value={quant.profitability.roce != null ? `${(quant.profitability.roce * 100).toFixed(2)}%` : 'N/A'} />
              <MetricCard label="Price to Book (P/B)" value={quant.valuation.pb_ratio != null ? quant.valuation.pb_ratio.toFixed(2) : 'N/A'} />
              <MetricCard label="Dividend Yield" value={quant.dividend.dividend_yield != null ? `${(quant.dividend.dividend_yield * 100).toFixed(2)}%` : 'N/A'} />
              <MetricCard label="PEG Ratio" value={quant.valuation.peg_ratio != null ? quant.valuation.peg_ratio.toFixed(2) : 'N/A'} />
            </div>
          </div>
        )}

        {/* Section 2: Price Chart */}
        {chartData && chartData.series && chartData.series.length > 0 && (
          <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Historical Price Trend</h2>
              <div className="flex space-x-1 text-xs">
                {['1mo', '3mo', '1y'].map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-2.5 py-1 rounded transition-colors ${
                      period === p ? 'bg-[#14251B] text-cream font-medium border border-hairline' : 'text-cream-muted hover:text-cream'
                    }`}
                  >
                    {p.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ReLineChart data={chartData.series}>
                  <XAxis dataKey="timestamp" stroke="#C4BCAD" fontSize={10} tickLine={false} />
                  <YAxis stroke="#C4BCAD" fontSize={10} domain={['auto', 'auto']} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#0D1912', borderColor: 'rgba(245,239,230,0.12)', borderRadius: '8px', fontSize: '12px', color: '#F5EFE6' }} />
                  <Line type="monotone" dataKey="close" stroke="#3D7A56" strokeWidth={2} dot={false} />
                </ReLineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Section 3: News Feed */}
        {newsList && newsList.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Latest News</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {newsList.map((art) => (
                <div key={art.id} className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-2 shadow-sm">
                  <div className="text-xs text-cream-muted flex items-center justify-between font-mono tabular-nums">
                    <div className="flex items-center space-x-2">
                      <span>{art.source}</span>
                      <span className="bg-accent/20 text-accent px-1.5 py-0.5 rounded text-[10px]">${art.canonical_symbol || targetSymbol}</span>
                    </div>
                    <span>{art.published_time ? new Date(art.published_time).toLocaleDateString() : ''}</span>
                  </div>
                  <h3 className="text-sm font-medium text-cream">{art.headline}</h3>
                  <p className="ai-answer-serif text-xs text-cream-muted line-clamp-2">{art.summary}</p>
                  <div className="pt-2 mt-2 border-t border-hairline flex justify-end">
                    <a href={art.url} target="_blank" rel="noopener noreferrer" className="flex items-center space-x-1 text-xs text-accent hover:underline">
                      <span>Original Article</span>
                      <ExternalLink className="w-3 h-3" />
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
