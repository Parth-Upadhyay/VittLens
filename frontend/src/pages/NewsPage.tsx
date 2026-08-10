import React, { useState, useEffect } from 'react';
import { NewsService } from '../services/api';
import { NewsArticle } from '../types';
import { Newspaper, ExternalLink, Filter } from 'lucide-react';

const SYMBOLS = [
  'ALL', 'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',
  'BHARTIARTL', 'SBIN', 'ITC', 'LT', 'BAJFINANCE',
  'HCLTECH', 'TATAMOTORS', 'TATASTEEL', 'NTPC', 'MARUTI', 'AXISBANK',
  'KOTAKBANK', 'SUNPHARMA', 'WIPRO', 'ADANIENT', 'JIOFIN', 'ZOMATO'
];

export const NewsPage: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('ALL');
  const [searchInput, setSearchInput] = useState('ALL');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    const sym = selectedSymbol === 'ALL' ? undefined : selectedSymbol;
    NewsService.getNews(sym, 50)
      .then((data) => setArticles(data))
      .catch((e) => console.error('Failed to load news:', e))
      .finally(() => setIsLoading(false));
  }, [selectedSymbol]);

  const filteredSymbols = SYMBOLS.filter(s => s.toLowerCase().includes(searchInput.toLowerCase()));

  return (
    <div className="flex-1 p-8 w-full max-w-[1400px] mx-auto space-y-6 font-sans bg-bg-primary animate-page-in">
      {/* Header & Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <Newspaper className="w-5 h-5 text-accent" />
          <h1 className="text-2xl font-heading font-semibold text-tx-primary tracking-tight">Market Intelligence</h1>
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-tx-tertiary" />
          <span className="text-xs text-tx-secondary">Filter:</span>
          <div className="relative">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value.toUpperCase());
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setSelectedSymbol(searchInput || 'ALL');
                  setShowSuggestions(false);
                }
              }}
              placeholder="Search or add symbol..."
              className="bg-bg-input border border-border text-xs text-tx-primary rounded-lg px-3 py-1.5 input-glow font-sans w-48"
            />
            {showSuggestions && (
              <div className="absolute z-50 top-full mt-1 w-full surface-elevated max-h-48 overflow-y-auto">
                {filteredSymbols.length > 0 ? (
                  filteredSymbols.map((s) => (
                    <div
                      key={s}
                      onClick={() => {
                        setSelectedSymbol(s);
                        setSearchInput(s);
                        setShowSuggestions(false);
                      }}
                      className="px-3 py-2 text-xs text-tx-primary hover:bg-bg-hover cursor-pointer nav-transition"
                    >
                      {s}
                    </div>
                  ))
                ) : (
                  <div
                    onClick={() => {
                      if (searchInput.trim()) {
                        setSelectedSymbol(searchInput.trim().toUpperCase());
                        setShowSuggestions(false);
                      }
                    }}
                    className="px-3 py-2 text-xs text-accent bg-accent-light hover:bg-bg-hover cursor-pointer font-medium nav-transition"
                  >
                    + Search "{searchInput}"
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* News Grid */}
      {isLoading ? (
        <div className="py-12 text-center text-sm text-tx-secondary font-sans">Loading news articles...</div>
      ) : articles.length === 0 ? (
        <div className="py-12 text-center text-sm text-tx-secondary font-sans">No news articles found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {articles.map((art) => (
            <div
              key={art.id}
              className="surface-card p-6 space-y-3 card-interactive flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-tx-secondary">
                  <div className="flex items-center space-x-2">
                    <span className="bg-accent text-white px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-medium">{art.source}</span>
                    <span className="font-mono text-[10px] text-accent bg-accent-light px-1.5 py-0.5 rounded">${art.canonical_symbol || art.symbol}</span>
                  </div>
                  <span className="text-tx-tertiary font-mono text-[10px]">{art.published_time ? new Date(art.published_time).toLocaleDateString() : 'Recent'}</span>
                </div>

                <h3 className="text-[15px] font-semibold text-tx-primary leading-snug">{art.headline}</h3>

                <p className="text-sm text-tx-secondary line-clamp-3 leading-relaxed">
                  {art.summary}
                </p>
              </div>

              <div className="pt-3 border-t border-border flex items-center justify-end text-xs text-tx-secondary">
                <a
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-accent hover:underline nav-transition"
                >
                  <span>Read original</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
