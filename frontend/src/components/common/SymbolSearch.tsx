import React, { useState, useEffect, useRef } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { Search, X } from 'lucide-react';

interface SymbolSearchProps {
  onSelect: (symbol: string) => void;
  placeholder?: string;
  className?: string;
  clearOnSelect?: boolean;
}

export const SymbolSearch: React.FC<SymbolSearchProps> = ({ 
  onSelect, 
  placeholder = "Search for a company...", 
  className = "",
  clearOnSelect = true,
}) => {
  const { marketSymbols, preferences } = useAppStore();
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<{ canonical: string; match: string }[]>([]);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && !query) {
      const defaultResults = (preferences.default_symbols || []).map(sym => ({
        canonical: sym,
        match: sym
      }));
      setResults(defaultResults);
      return;
    }

    if (!query) {
      setResults([]);
      return;
    }

    const lowerQuery = query.toLowerCase();
    const matched: { canonical: string; match: string }[] = [];

    for (const [canonical, aliases] of Object.entries(marketSymbols)) {
      if (canonical.toLowerCase().includes(lowerQuery)) {
        matched.push({ canonical, match: canonical });
        if (matched.length >= 15) break;
        continue;
      }
      
      const foundAlias = aliases.find(a => a.toLowerCase().includes(lowerQuery));
      if (foundAlias) {
        matched.push({ canonical, match: foundAlias });
        if (matched.length >= 15) break;
      }
    }

    setResults(matched);
  }, [query, isOpen, marketSymbols, preferences.default_symbols]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSelect = (canonical: string) => {
    onSelect(canonical);
    if (clearOnSelect) {
      setQuery('');
    } else {
      setQuery(canonical);
    }
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && results.length > 0) {
      e.preventDefault();
      handleSelect(results[0].canonical);
    }
  };

  return (
    <div ref={wrapperRef} className={`relative flex items-center ${className}`}>
      <Search className="absolute left-3 w-4 h-4 text-tx-tertiary" />
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setIsOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full bg-bg-input border border-border text-xs text-tx-primary placeholder-tx-tertiary rounded-lg pl-9 pr-8 py-2 input-glow font-sans"
      />
      {query && (
        <button 
          onClick={() => setQuery('')} 
          className="absolute right-3 p-1 text-tx-tertiary hover:text-tx-primary nav-transition"
          type="button"
        >
           <X className="w-3 h-3" />
        </button>
      )}

      {isOpen && (
        <ul className="absolute z-50 top-full left-0 right-0 mt-1 surface-elevated max-h-60 overflow-y-auto">
          {results.length > 0 ? (
            results.map((r, i) => (
              <li
                key={`${r.canonical}-${i}`}
                onClick={() => handleSelect(r.canonical)}
                className="px-4 py-2.5 cursor-pointer hover:bg-bg-hover flex flex-col border-b border-border last:border-b-0 nav-transition"
              >
                <span className="text-xs font-medium text-tx-primary">{r.canonical}</span>
                {r.canonical !== r.match && (
                  <span className="text-[10px] text-tx-secondary truncate capitalize">{r.match}</span>
                )}
              </li>
            ))
          ) : (
            <li className="px-4 py-3 text-xs text-tx-secondary text-center">No symbols found</li>
          )}
        </ul>
      )}
    </div>
  );
};
