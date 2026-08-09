import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/useAppStore';
import { MarketService, WatchlistService, NewsService } from '../services/api';
import { StockQuote, HistoricalData, NewsArticle } from '../types';
import { MiniSparkline } from '../components/visual/MiniSparkline';
import { SymbolSearch } from '../components/common/SymbolSearch';
import { LayoutDashboard, Plus, Trash2, ExternalLink } from 'lucide-react';

// Removed DEFAULT_DASHBOARD_SYMBOLS fallback to allow empty states

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { watchlist, fetchWatchlist } = useAppStore();
  const [quotes, setQuotes] = useState<Record<string, StockQuote>>({});
  const [charts, setCharts] = useState<Record<string, HistoricalData>>({});
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [newSymbol, setNewSymbol] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const loadQuotes = async () => {
      setIsLoading(true);
      const dict: Record<string, StockQuote> = {};
      const chartDict: Record<string, HistoricalData> = {};
      const symbolsToFetch = watchlist.map((w) => w.symbol);

      try {
        if (symbolsToFetch.length > 0) {
          const newsPromises = symbolsToFetch.map(sym => NewsService.getNews(sym, 3));
          const newsResults = await Promise.allSettled(newsPromises);
          let combinedNews: NewsArticle[] = [];
          newsResults.forEach(res => {
            if (res.status === 'fulfilled' && res.value) {
              combinedNews = [...combinedNews, ...res.value];
            }
          });
          combinedNews.sort((a, b) => new Date(b.published_time || 0).getTime() - new Date(a.published_time || 0).getTime());
          setNews(combinedNews.slice(0, 6));
        } else {
          setNews([]);
        }
      } catch (e) {
        console.error('Failed to fetch news:', e);
        setNews([]);
      }

      for (const sym of symbolsToFetch) {
        try {
          const [quote, chart] = await Promise.all([
            MarketService.getQuote(sym),
            MarketService.getChart(sym, '1mo')
          ]);
          dict[sym] = quote;
          chartDict[sym] = chart;
        } catch (e) {
          console.error(`Failed to fetch data for ${sym}:`, e);
          // Skip adding this symbol to dashboard
        }
      }
      setQuotes(dict);
      setCharts(chartDict);
      setIsLoading(false);
    };

    loadQuotes();
  }, [watchlist]);

  const handleSelectSymbol = async (canonical: string) => {
    if (!canonical.trim()) return;
    setErrorMsg(null);

    try {
      // Add symbol via watchlist API
      await WatchlistService.addSymbol(canonical);

      // Immediately fetch quote for newly added symbol and insert into local state
      try {
        const [quote, chart] = await Promise.all([
          MarketService.getQuote(canonical),
          MarketService.getChart(canonical, '1mo')
        ]);
        setQuotes((prev) => ({ ...prev, [canonical]: quote }));
        setCharts((prev) => ({ ...prev, [canonical]: chart }));
      } catch (qErr) {
        console.error('Failed to fetch quote for added symbol:', qErr);
        // Skip adding this symbol to dashboard
      }

      await fetchWatchlist();
    } catch (err: any) {
      console.error('Failed to add watchlist item:', err);
      setErrorMsg('Failed to add symbol. Please verify symbol ticker.');
    }
  };

  const handleRemoveWatchlist = async (e: React.MouseEvent, symbol: string) => {
    e.preventDefault();
    e.stopPropagation();

    // Optimistically update local quotes state for immediate visual removal
    setQuotes((prev) => {
      const copy = { ...prev };
      delete copy[symbol];
      return copy;
    });
    setCharts((prev) => {
      const copy = { ...prev };
      delete copy[symbol];
      return copy;
    });

    try {
      await WatchlistService.removeSymbol(symbol);
      await fetchWatchlist();
    } catch (err) {
      console.error('Failed to remove watchlist item:', err);
    }
  };

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">
      {/* Professional Title Bar without Emojis or Bounding Box */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div className="flex items-center space-x-2.5">
          <LayoutDashboard className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-medium text-cream tracking-tight">Market Watchlist & Overview</h1>
        </div>

        {/* Add Symbol Search */}
        <div className="w-64">
          <SymbolSearch 
            onSelect={handleSelectSymbol} 
            placeholder="Search company (e.g. INFY, TCS)"
          />
        </div>
      </div>

      {errorMsg && (
        <div className="p-2.5 rounded bg-semantic-red/10 border border-semantic-red/30 text-semantic-red text-xs font-sans">
          {errorMsg}
        </div>
      )}

      {/* Watchlist Overview Grid */}
      <div className="space-y-3">
        <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Watchlist Overview</h2>

        {isLoading ? (
          <div className="py-12 text-center text-xs text-cream-muted font-sans">Loading market quotes...</div>
        ) : Object.keys(quotes).length === 0 ? (
          <div className="py-12 text-center text-xs text-cream-muted font-sans">No symbols in watchlist. Add a symbol above.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {Object.entries(quotes).map(([sym, quote]) => {
              const isGain = quote.change >= 0;
              return (
                <div
                  key={sym}
                  onClick={() => navigate(`/company/${sym}`)}
                  className="bg-[#0D1912] border border-hairline rounded-xl p-4 hover:border-accent/60 transition-colors cursor-pointer space-y-3 relative group shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-mono text-sm font-medium text-cream">{sym}</div>
                      <div className="text-[11px] text-cream-muted">NSE • INR</div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => handleRemoveWatchlist(e, sym)}
                      className="p-1.5 text-cream-dim hover:text-semantic-red transition-colors rounded hover:bg-[#14251B]"
                      title={`Remove ${sym} from watchlist`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="flex items-baseline justify-between">
                    <div>
                      <span className="text-lg font-medium text-cream font-mono tabular-nums">₹{quote.price.toLocaleString()}</span>
                      <div className={`text-xs font-mono tabular-nums ${isGain ? 'text-semantic-green' : 'text-semantic-red'}`}>
                        {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)} ({quote.change_percent.toFixed(2)}%)
                      </div>
                    </div>

                    {/* Single Accent Line Sparkline */}
                    <MiniSparkline data={charts[sym]?.series ? charts[sym].series.map(b => b.close) : []} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Market News Section */}
      <div className="space-y-3 pt-6 border-t border-hairline mt-6">
        <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Market News</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(news || []).map((art) => (
            <div key={art.id} className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-2 shadow-sm flex flex-col justify-between hover:border-accent/60 transition-colors">
              <div>
                <div className="text-[10px] text-cream-muted flex items-center justify-between font-mono tabular-nums mb-2">
                  <div className="flex items-center space-x-2">
                    <span>{art.source}</span>
                    <span className="bg-accent/20 text-accent px-1.5 py-0.5 rounded text-[10px]">${art.canonical_symbol || 'MKT'}</span>
                  </div>
                  <span>{art.published_time ? new Date(art.published_time).toLocaleDateString() : ''}</span>
                </div>
                <h3 className="text-sm font-medium text-cream line-clamp-2 leading-snug">{art.headline}</h3>
                <p className="ai-answer-serif text-xs text-cream-muted line-clamp-3 mt-1.5">{art.summary}</p>
              </div>
              <div className="pt-3 mt-3 border-t border-hairline flex justify-end">
                <a
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-xs text-accent hover:underline"
                >
                  <span>Original Article</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          ))}
          {(!news || news.length === 0) && !isLoading && (
            <div className="col-span-full py-8 text-center text-xs text-cream-muted font-sans">No recent news available.</div>
          )}
        </div>
      </div>
    </div>
  );
};
