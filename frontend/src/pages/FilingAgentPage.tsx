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
    <div className="flex-1 p-8 w-full max-w-[1200px] mx-auto space-y-8 font-sans bg-bg-primary overflow-y-auto animate-page-in">

      {/* Header */}
      <div className="flex items-center space-x-3 pb-2">
        <div className="w-10 h-10 rounded-lg bg-accent-light border border-accent/20 flex items-center justify-center">
          <FileText className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-semibold text-tx-primary tracking-tight">Filing Agent</h1>
          <p className="text-sm text-tx-secondary">AI-powered semantic search across corporate annual reports</p>
        </div>
      </div>

      {/* Free Tier Notice */}
      <div className="alert-warm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2 text-sm font-semibold text-semantic-amber font-heading">
            <AlertCircle className="w-5 h-5" />
            <span>NIFTY 20 Coverage Limit</span>
          </div>
        </div>
        <div className="space-y-3">
          <p className="text-sm text-tx-primary ai-answer-serif leading-relaxed">
            Annual reports are stored in our Qdrant vector database. The Filing Agent can answer deep questions about revenue, segments, risks, debt, capex, and more — but only for the 20 companies below. Expanding coverage is on the roadmap!
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {NIFTY20_SYMBOLS.map(sym => (
              <button
                key={sym}
                onClick={() => setSelectedSymbol(sym)}
                className={`text-xs font-mono px-3 py-1 rounded transition-colors border nav-transition btn-press ${
                  selectedSymbol === sym
                    ? 'bg-accent text-white border-accent-hover'
                    : 'bg-bg-secondary text-tx-secondary border-border hover:text-tx-primary hover:border-border-strong'
                }`}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Search Panel */}
      <div className="surface-card p-6 space-y-6 shadow-sm">
        <h2 className="metric-label">Query Annual Reports</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="space-y-2">
            <label className="text-[11px] text-tx-secondary uppercase tracking-wider font-semibold">Company (optional)</label>
            <SymbolSearch
              onSelect={setSelectedSymbol}
              placeholder="Filter by company..."
              clearOnSelect={false}
            />
            {selectedSymbol && !isNifty20 && (
              <div className="text-xs text-semantic-amber flex items-center space-x-1.5 pt-1">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>No annual report for {selectedSymbol}. Search will scan all NIFTY 20 reports.</span>
              </div>
            )}
            {selectedSymbol && isNifty20 && (
              <div className="text-xs text-semantic-green flex items-center space-x-1.5 pt-1">
                <span>✓ Annual report available for {selectedSymbol}</span>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-[11px] text-tx-secondary uppercase tracking-wider font-semibold">Sample Questions</label>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_QUERIES.map(q => (
                <button
                  key={q}
                  onClick={() => setQuery(q)}
                  className="text-xs bg-bg-secondary border border-border text-tx-secondary hover:text-tx-primary hover:bg-bg-hover hover:border-border-strong px-3 py-1.5 rounded-lg nav-transition"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row items-start space-y-3 sm:space-y-0 sm:space-x-3 pt-2">
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
            className="flex-1 w-full bg-bg-input border border-border text-sm text-tx-primary placeholder-tx-tertiary rounded-xl px-4 py-3 input-glow font-sans resize-none"
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium px-6 py-3 rounded-xl flex items-center justify-center space-x-2 shadow-sm nav-transition btn-press sm:h-[82px]"
          >
            <Send className="w-4 h-4" />
            <span>{isLoading ? 'Searching...' : 'Search'}</span>
          </button>
        </form>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex flex-col items-center py-16 space-y-4">
          <Sparkles className="w-8 h-8 text-accent animate-pulse" />
          <div className="text-sm font-medium text-tx-primary">Searching Qdrant vector database...</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alert-danger text-sm text-semantic-red">
          {error}
        </div>
      )}

      {/* Answer */}
      {answer && (
        <div className="surface-card overflow-hidden animate-page-in">
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
        <div className="flex flex-col items-center py-24 space-y-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent-light border border-accent/20 flex items-center justify-center">
            <FileText className="w-8 h-8 text-accent" />
          </div>
          <div>
            <div className="text-lg font-heading font-semibold text-tx-primary">Ask anything about annual reports</div>
            <div className="text-sm text-tx-secondary mt-1 max-w-md mx-auto">Type your question above. The Filing Agent searches through embedded annual report chunks using semantic vector search.</div>
          </div>
        </div>
      )}

    </div>
  );
};
