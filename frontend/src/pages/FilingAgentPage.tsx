import React, { useState } from 'react';
import { FileText, Send, BookOpen, AlertCircle, Sparkles } from 'lucide-react';
import { ChatService } from '../services/api';
import { SymbolSearch } from '../components/common/SymbolSearch';
import { MessageItem } from '../components/chat/MessageItem';

// The 20 NIFTY companies for which we have annual reports
const NIFTY20_SYMBOLS = [
  'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
  'BHARTIARTL', 'SBIN', 'BAJFINANCE', 'ADANIENT',
  'KOTAKBANK', 'ITC', 'LT', 'ASIANPAINT', 'AXISBANK',
  'MARUTI', 'TITAN', 'WIPRO', 'NTPC', 'ULTRACEMCO',
];

const SAMPLE_QUERIES = [
  'What were the key revenue drivers this year?',
  'How is the debt profile and leverage trending?',
  'What are the main business risks highlighted?',
  'Summarise segment-wise performance',
  'What is the dividend policy and payout history?',
  'What capital expenditure plans are mentioned?',
];

export const FilingAgentPage: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState<string | null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setIsLoading(true);
    setAnswer(null);
    setSources([]);
    setError(null);

    try {
      const res = await ChatService.sendQuery({
        question: selectedSymbol
          ? `Search the annual report filing for ${selectedSymbol}: ${query}`
          : `Search annual report filings: ${query}`,
        symbols: selectedSymbol ? [selectedSymbol] : [],
      });
      setAnswer(res.answer);
      setSources(res.sources || []);
    } catch {
      setError('Could not reach the filing search service. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const isNifty20 = selectedSymbol && NIFTY20_SYMBOLS.includes(selectedSymbol.toUpperCase());

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">

      {/* Header */}
      <div className="flex items-center space-x-3 pb-2">
        <div className="w-9 h-9 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
          <FileText className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-medium text-cream tracking-tight">Filing Agent</h1>
          <p className="text-xs text-cream-muted">AI-powered search across annual report filings</p>
        </div>
      </div>

      {/* Free Tier Notice */}
      <div className="bg-[#0D1912] border border-accent/20 rounded-xl p-4 flex items-start space-x-3">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
          <AlertCircle className="w-4 h-4 text-accent" />
        </div>
        <div className="space-y-1">
          <div className="text-xs font-medium text-cream">We only have NIFTY 20 Annual Reports due to free tier limits and I'm a student :)</div>
          <div className="text-xs text-cream-muted leading-relaxed">
            Annual reports are stored in our Qdrant vector database. The Filing Agent can answer deep questions about revenue, segments, risks, debt, capex, and more — but only for the 20 companies below. Expanding coverage is on the roadmap!
          </div>
          <div className="flex flex-wrap gap-1.5 pt-2">
            {NIFTY20_SYMBOLS.map(sym => (
              <button
                key={sym}
                onClick={() => setSelectedSymbol(sym)}
                className={`text-[10px] font-mono px-2 py-0.5 rounded transition-colors border ${
                  selectedSymbol === sym
                    ? 'bg-accent/20 text-cream border-accent/40'
                    : 'bg-[#14251B]/50 text-cream-muted border-hairline hover:text-cream hover:border-accent/30'
                }`}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Search Panel */}
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm">
        <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Query Annual Reports</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] text-cream-muted uppercase tracking-wider">Company (optional)</label>
            <SymbolSearch
              onSelect={setSelectedSymbol}
              placeholder="Filter by company..."
              clearOnSelect={false}
            />
            {selectedSymbol && !isNifty20 && (
              <div className="text-[10px] text-amber-400 flex items-center space-x-1 pt-0.5">
                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                <span>No annual report for {selectedSymbol}. Search will scan all NIFTY 20 reports.</span>
              </div>
            )}
            {selectedSymbol && isNifty20 && (
              <div className="text-[10px] text-semantic-green flex items-center space-x-1 pt-0.5">
                <span>✓ Annual report available for {selectedSymbol}</span>
              </div>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-[10px] text-cream-muted uppercase tracking-wider">Sample Questions</label>
            <div className="flex flex-wrap gap-1.5">
              {SAMPLE_QUERIES.map(q => (
                <button
                  key={q}
                  onClick={() => setQuery(q)}
                  className="text-[10px] bg-[#14251B]/60 border border-hairline text-cream-muted hover:text-cream hover:border-accent/30 px-2 py-1 rounded transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        <form onSubmit={handleSearch} className="flex items-start space-x-2 pt-2">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch(e as any);
              }
            }}
            placeholder="Ask anything about the annual report — revenue drivers, risks, capex, segment performance, debt strategy..."
            rows={3}
            className="flex-1 bg-[#14251B] border border-hairline text-xs text-cream placeholder-cream-dim rounded-lg px-3 py-2.5 focus:outline-none focus:border-accent font-sans resize-none"
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-cream text-xs font-medium px-4 py-2.5 rounded-lg flex items-center space-x-1.5 shadow-sm transition-colors flex-shrink-0"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Searching...' : 'Search'}</span>
          </button>
        </form>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex flex-col items-center py-12 space-y-3">
          <Sparkles className="w-7 h-7 text-accent animate-pulse" />
          <div className="text-xs text-cream-muted">Searching Qdrant vector database...</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-[#1A0A0A] border border-semantic-red/30 rounded-xl p-4 text-xs text-semantic-red text-center">
          {error}
        </div>
      )}

      {/* Answer */}
      {answer && (
        <div className="border border-hairline rounded-xl overflow-hidden shadow-sm">
          <MessageItem 
            role="assistant" 
            content={answer} 
            sources={sources} 
            agents_used={['FilingAgent']}
            symbols_queried={selectedSymbol ? [selectedSymbol] : []}
          />
        </div>
      )}

      {/* Empty state */}
      {!answer && !isLoading && !error && (
        <div className="flex flex-col items-center py-20 space-y-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent/5 border border-accent/10 flex items-center justify-center">
            <FileText className="w-8 h-8 text-accent/40" />
          </div>
          <div>
            <div className="text-sm font-medium text-cream-muted">Ask anything about annual reports</div>
            <div className="text-xs text-cream-dim mt-1 max-w-sm">Type your question above. The Filing Agent searches through embedded annual report chunks using semantic vector search.</div>
          </div>
        </div>
      )}

    </div>
  );
};
