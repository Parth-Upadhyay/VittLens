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
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">
      {/* Header & Filter Bar without Emojis or Bounding Box */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div className="flex items-center space-x-2.5">
          <Newspaper className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-medium text-cream tracking-tight">Market Intelligence & News Feed</h1>
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-cream-muted" />
          <span className="text-xs text-cream-muted">Filter Company:</span>
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
              className="bg-[#0D1912] border border-hairline text-xs text-cream rounded-lg px-3 py-1.5 focus:outline-none focus:border-accent font-sans w-48"
            />
            {showSuggestions && (
              <div className="absolute z-50 top-full mt-1 w-full bg-[#0D1912] border border-hairline rounded-lg shadow-lg max-h-48 overflow-y-auto scrollbar-thin">
                {filteredSymbols.length > 0 ? (
                  filteredSymbols.map((s) => (
                    <div
                      key={s}
                      onClick={() => {
                        setSelectedSymbol(s);
                        setSearchInput(s);
                        setShowSuggestions(false);
                      }}
                      className="px-3 py-2 text-xs text-cream hover:bg-accent/20 hover:text-cream cursor-pointer"
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
                    className="px-3 py-2 text-xs text-cream bg-accent/10 hover:bg-accent/20 cursor-pointer font-medium"
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
        <div className="py-12 text-center text-xs text-cream-muted font-sans">Loading AI news articles...</div>
      ) : articles.length === 0 ? (
        <div className="py-12 text-center text-xs text-cream-muted font-sans">No news articles found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {articles.map((art) => (
            <div
              key={art.id}
              className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-3 hover:border-accent/40 transition-colors flex flex-col justify-between shadow-sm"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-cream-muted">
                  <span className="font-mono bg-accent/20 text-accent px-1.5 py-0.5 rounded font-medium tabular-nums">${art.canonical_symbol || art.symbol}</span>
                  <span className="font-mono tabular-nums">{art.published_time ? new Date(art.published_time).toLocaleDateString() : 'Recent'}</span>
                </div>

                <h3 className="text-sm font-medium text-cream leading-snug">{art.headline}</h3>

                {/* AI Summary in Serif */}
                <p className="ai-answer-serif text-xs text-cream-muted line-clamp-3 leading-relaxed">
                  {art.summary}
                </p>
              </div>

              <div className="pt-2 border-t border-hairline flex items-center justify-between text-xs text-cream-muted">
                <span className="text-[11px] text-cream-dim">Source: {art.source}</span>
                <a
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-accent hover:underline"
                >
                  <span>Original Article</span>
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
