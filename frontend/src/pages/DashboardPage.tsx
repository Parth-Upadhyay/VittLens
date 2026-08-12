import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/useAppStore';
import { MarketService, WatchlistService, NewsService } from '../services/api';
import { StockQuote, HistoricalData, NewsArticle } from '../types';
import { SymbolSearch } from '../components/common/SymbolSearch';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { LayoutDashboard, Plus, Trash2, ExternalLink, Triangle } from 'lucide-react';

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
    let isActive = true;

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
          let hasSuccess = false;
          
          newsResults.forEach(res => {
            if (res.status === 'fulfilled' && res.value) {
              combinedNews = [...combinedNews, ...res.value];
              hasSuccess = true;
            }
          });
          
          if (isActive) {
            if (hasSuccess) {
              combinedNews.sort((a, b) => new Date(b.published_time || 0).getTime() - new Date(a.published_time || 0).getTime());
              setNews(combinedNews.slice(0, 6));
            }
          }
        } else {
          if (isActive) setNews([]);
        }
      } catch (e) {
        console.error('Failed to fetch news:', e);
      }

      for (const sym of symbolsToFetch) {
        if (!isActive) break;
        try {
          const [quote, chart] = await Promise.all([
            MarketService.getQuote(sym),
            MarketService.getChart(sym, '1mo')
          ]);
          dict[sym] = quote;
          chartDict[sym] = chart;
        } catch (e) {
          console.error(`Failed to fetch data for ${sym}:`, e);
        }
      }
      
      if (isActive) {
        setQuotes(dict);
        setCharts(chartDict);
        setIsLoading(false);
      }
    };

    loadQuotes();
    
    return () => {
      isActive = false;
    };
  }, [watchlist]);

  const handleSelectSymbol = async (canonical: string) => {
    if (!canonical.trim()) return;
    setErrorMsg(null);

    const isGuest = useAppStore.getState().user === null;

    try {
      if (isGuest) {
        const stored = sessionStorage.getItem('vittlens_guest_watchlist');
        const list = stored ? JSON.parse(stored) : [];
        if (!list.some((item: any) => item.symbol === canonical)) {
          list.push({
            id: Date.now(),
            symbol: canonical,
            created_at: new Date().toISOString()
          });
          sessionStorage.setItem('vittlens_guest_watchlist', JSON.stringify(list));
        }
      } else {
        await WatchlistService.addSymbol(canonical);
      }

      try {
        const [quote, chart] = await Promise.all([
          MarketService.getQuote(canonical),
          MarketService.getChart(canonical, '1mo')
        ]);
        setQuotes((prev) => ({ ...prev, [canonical]: quote }));
        setCharts((prev) => ({ ...prev, [canonical]: chart }));
      } catch (qErr) {
        console.error('Failed to fetch quote for added symbol:', qErr);
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

    const isGuest = useAppStore.getState().user === null;

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
      if (isGuest) {
        const stored = sessionStorage.getItem('vittlens_guest_watchlist');
        let list = stored ? JSON.parse(stored) : [];
        list = list.filter((item: any) => item.symbol !== symbol);
        sessionStorage.setItem('vittlens_guest_watchlist', JSON.stringify(list));
      } else {
        await WatchlistService.removeSymbol(symbol);
      }
      await fetchWatchlist();
    } catch (err) {
      console.error('Failed to remove watchlist item:', err);
    }
  };

  return (
    <div className="flex-1 p-4 md:p-8 w-full max-w-[1400px] mx-auto space-y-6 md:space-y-8 font-sans bg-bg-primary animate-page-in">
      {/* Title Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <LayoutDashboard className="w-5 h-5 text-accent flex-shrink-0" />
          <h1 className="text-xl md:text-2xl font-heading font-semibold text-tx-primary tracking-tight">Market Watchlist</h1>
        </div>

        <div className="w-full sm:w-64">
          <SymbolSearch 
            onSelect={handleSelectSymbol} 
            placeholder="Search company (e.g. INFY, TCS)"
          />
        </div>
      </div>

      {errorMsg && (
        <div className="alert-warm text-sm text-semantic-amber">
          {errorMsg}
        </div>
      )}

      {/* Watchlist Overview Grid */}
      <div className="space-y-4">
        <h2 className="metric-label">Watchlist Overview</h2>

        {watchlist.length === 0 && isLoading ? (
          <LoadingSpinner message="Loading market quotes..." />
        ) : watchlist.length === 0 ? (
          <div className="py-12 text-center text-sm text-tx-secondary font-sans">No symbols in watchlist. Add a symbol above.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
            {watchlist.map((wItem) => {
              const sym = wItem.symbol;
              const quote = quotes[sym];

              if (isLoading) {
                return (
                  <div key={sym} className="surface-card p-6 flex flex-col justify-center items-center h-full min-h-[140px] relative group">
                    <LoadingSpinner />
                  </div>
                );
              }

              if (!quote) {
                return (
                  <div key={sym} className="surface-card p-6 flex flex-col justify-center items-center h-full min-h-[140px] relative group">
                    <button
                      type="button"
                      onClick={(e) => handleRemoveWatchlist(e, sym)}
                      className="absolute top-4 right-4 p-1.5 text-tx-tertiary hover:text-semantic-red nav-transition rounded hover:bg-bg-hover"
                      title={`Remove ${sym} from watchlist`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <span className="text-xs text-tx-secondary font-mono tracking-wide">Data Unavailable for {sym}</span>
                  </div>
                );
              }

              const isGain = quote.change >= 0;
              return (
                <div
                  key={sym}
                  onClick={() => navigate(`/company/${sym}`)}
                  className="surface-card p-6 card-interactive cursor-pointer space-y-3 relative group flex flex-col justify-between h-full min-h-[140px]"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-mono text-sm font-medium text-tx-primary">{sym}</div>
                      <div className="text-[11px] text-tx-tertiary">NSE • INR</div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => handleRemoveWatchlist(e, sym)}
                      className="p-1.5 text-tx-tertiary hover:text-semantic-red nav-transition rounded hover:bg-bg-hover"
                      title={`Remove ${sym} from watchlist`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="flex flex-col gap-2">
                    <div className="flex items-baseline justify-between">
                      <div className="flex flex-col">
                        <span className="text-xl font-semibold text-tx-primary font-mono">
                          {quote.price != null ? `₹${quote.price.toLocaleString()}` : 'N/A'}
                        </span>
                        {quote.change != null && quote.change_percent != null && (
                          <span className={`text-xs font-mono font-medium ${isGain ? 'text-semantic-green' : 'text-semantic-red'}`}>
                            {isGain ? '+' : ''}{quote.change.toFixed(2)} ({isGain ? '+' : ''}{quote.change_percent.toFixed(2)}%)
                          </span>
                        )}
                      </div>
                      {quote.change != null && (
                        <div className="flex items-center justify-center pr-2">
                          <Triangle 
                            className={`w-7 h-7 drop-shadow-sm transition-colors ${
                              isGain ? 'text-semantic-green fill-current' : 'text-semantic-red fill-current rotate-180'
                            }`}
                          />
                        </div>
                      )}
                    </div>

                    <div className="pt-2 border-t border-border flex justify-end">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          navigate(`/deep-analyze?symbol=${sym}`);
                        }}
                        className="flex items-center space-x-1 text-[11px] font-medium text-accent hover:text-accent-hover bg-bg-tertiary hover:bg-bg-hover px-2.5 py-1.5 rounded nav-transition"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Deep Analyze</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Market News Section */}
      <div className="space-y-4 pt-8 border-t border-border">
        <h2 className="metric-label">Market News</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {(news || []).map((art) => (
            <div key={art.id} className="surface-card p-6 space-y-3 flex flex-col justify-between card-interactive">
              <div>
                <div className="text-[11px] text-tx-secondary flex items-center justify-between font-sans mb-3">
                  <div className="flex items-center space-x-2">
                    <span className="bg-accent text-white px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium">{art.source}</span>
                    <span className="font-mono text-[10px] text-accent bg-accent-light px-1.5 py-0.5 rounded">${art.canonical_symbol || 'MKT'}</span>
                  </div>
                  <span className="text-tx-tertiary">{art.published_time ? new Date(art.published_time).toLocaleDateString() : ''}</span>
                </div>
                <h3 className="text-[15px] font-semibold text-tx-primary leading-snug">{art.headline}</h3>
                <p className="text-sm text-tx-secondary line-clamp-2 mt-2 leading-relaxed">{art.summary}</p>
              </div>
              <div className="pt-3 mt-3 border-t border-border flex justify-end">
                <a
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-xs text-accent hover:underline nav-transition"
                >
                  <span>Read original</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="col-span-full py-8 flex justify-center">
              <LoadingSpinner message="Fetching latest market news..." />
            </div>
          )}
          {(!news || news.length === 0) && !isLoading && (
            <div className="col-span-full py-8 text-center text-sm text-tx-secondary font-sans">No recent news available.</div>
          )}
        </div>
      </div>
    </div>
  );
};
