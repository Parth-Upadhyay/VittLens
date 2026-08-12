import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertTriangle, ExternalLink, Globe, TrendingUp, TrendingDown, User } from 'lucide-react';
import { MiniSparkline } from '../visual/MiniSparkline';
import { ImageCarousel } from './ImageCarousel';
import { useAppStore } from '../../store/useAppStore';
import { SourcesPanel, getCleanSiteName } from './SourcesPanel';
import { AgentChip } from './AgentChip';
import { MarketService } from '../../services/api';
import { HistoricalData, StockQuote } from '../../types';

// Custom component to render a rich chart directly in the chat bubble
const ChatChartBlock: React.FC<{ symbol: string }> = ({ symbol }) => {
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [chart, setChart] = useState<HistoricalData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchData = async () => {
      try {
        setLoading(true);
        const [q, c] = await Promise.all([
          MarketService.getQuote(symbol),
          MarketService.getChart(symbol, '1mo')
        ]);
        if (active) {
          setQuote(q);
          setChart(c);
        }
      } catch (err) {
        console.error("Failed to load chart for chat:", err);
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchData();
    return () => { active = false; };
  }, [symbol]);

  if (loading) {
    return (
      <div className="my-4 p-4 surface-card flex items-center justify-center h-[120px] rounded-xl border border-border">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-accent mb-2"></div>
          <span className="text-xs text-tx-secondary font-mono animate-pulse">Loading {symbol} chart...</span>
        </div>
      </div>
    );
  }

  if (!quote || !chart) return null;

  const isGain = quote.change >= 0;

  return (
    <div className="my-5 p-5 surface-card rounded-xl border border-border shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4 select-none">
      <div className="flex flex-col items-start w-full sm:w-1/3">
        <div className="flex items-center space-x-2 mb-1">
          <span className="font-mono font-semibold text-tx-primary text-sm tracking-wide">{symbol}</span>
          <span className="text-[10px] text-tx-tertiary bg-bg-tertiary px-1.5 py-0.5 rounded">1MO</span>
        </div>
        <div className="text-2xl font-semibold text-tx-primary font-mono tracking-tight">
          ₹{quote.price.toLocaleString()}
        </div>
        <div className={`flex items-center text-xs font-mono font-medium mt-1 ${isGain ? 'text-semantic-green' : 'text-semantic-red'}`}>
          {isGain ? <TrendingUp className="w-3.5 h-3.5 mr-1" /> : <TrendingDown className="w-3.5 h-3.5 mr-1" />}
          {isGain ? '+' : ''}{quote.change.toFixed(2)} ({quote.change_percent.toFixed(2)}%)
        </div>
      </div>
      <div className="w-full sm:w-2/3 h-[60px] flex justify-end">
        <div className="w-full max-w-[200px]">
          <MiniSparkline data={chart.series ? chart.series.map(b => b.close) : []} />
        </div>
      </div>
    </div>
  );
};

interface MessageItemProps {
  role: 'user' | 'assistant';
  content: string;
  images?: string[];
  sources?: string[];
  agents_used?: string[];
  symbols_queried?: string[];
  context_truncated?: boolean;
}

// Helper to format text containing financial numbers with IBM Plex Mono tabular numbers
const renderTextWithTabularNums = (text: string): React.ReactNode => {
  if (typeof text !== 'string') return text;

  // Regex matches prices, ratios, percentages, market caps
  const numberRegex = /(₹[\d,]+(?:\.\d+)?|\$[\d,]+(?:\.\d+)?[BMTK]?|[\d,]+\.\d+%?|[\d,]+%|[\d,]+(?:\.\d+)?x)/g;

  const parts = text.split(numberRegex);
  if (parts.length === 1) return text;

  return parts.map((part, i) => {
    if (part.match(numberRegex)) {
      return (
        <span key={i} className="font-mono tabular-nums text-tx-primary font-medium">
          {part}
        </span>
      );
    }
    return part;
  });
};

// Pre-processor converting raw URLs into clean Markdown link syntax
const convertRawUrlsToMarkdown = (text: string): string => {
  if (!text) return '';
  // Match standalone http/https URLs that are NOT already in markdown link brackets
  const rawUrlRegex = /(?<!\(|\=|\"|\'|\[)https?:\/\/[^\s\)\>]+/g;

  return text.replace(rawUrlRegex, (url) => {
    const cleanUrl = url.trim().replace(/[\,\.\)]+$/, '');
    const siteName = getCleanSiteName(cleanUrl);
    return `[${siteName}](${cleanUrl})`;
  });
};

// Pre-processor ensuring single-line compressed markdown tables are properly split into multi-line tables
const formatMarkdownTables = (text: string): string => {
  if (!text) return '';

  let formatted = convertRawUrlsToMarkdown(text);

  // Fix single-line compressed markdown tables (e.g. '| col | col | | --- | --- | | row | row |')
  formatted = formatted.replace(/\|\s*\|\s*/g, '|\n| ');

  // Standardize raw decimal ratio strings (e.g. ROE=0.1384 -> ROE: 13.84%)
  formatted = formatted.replace(/ROE=0\.(\d{2})(\d{2})/g, 'ROE: $1.$2%');
  formatted = formatted.replace(/Net Margin=0\.(\d{2})(\d{2})/g, 'Net Margin: $1.$2%');
  formatted = formatted.replace(/Gross Margin=0\.(\d{2})(\d{2})/g, 'Gross Margin: $1.$2%');
  formatted = formatted.replace(/Yield=(\d+(?:\.\d+)?)/g, 'Yield: $1%');
  formatted = formatted.replace(/([A-Za-z/]+)=([Nn]one|N\/A)/g, '$1: N/A');
  formatted = formatted.replace(/([A-Za-z/]+)=([\d.]+)/g, '$1: $2');

  return formatted;
};

// Helper stripping redundant disclaimer text and raw internal debug chunk dumps
const stripDisclaimersAndDebugTags = (text: string): string => {
  if (!text) return '';
  let cleaned = text;

  // Strip raw evidence chunk internal debug dumps
  cleaned = cleaned.replace(/\[Evidence Chunk[^\n]*\n?/gi, '');
  cleaned = cleaned.replace(/\|?\s*\[Evidence Chunk[\s\S]*?(?=\n\n|\n#|$)/gi, '');

  // Strip trailing disclaimer blocks
  cleaned = cleaned.replace(/(?:\n\n|\n)?(?:Disclaimer|Note):\s*The information provided[\s\S]*$/i, '');
  cleaned = cleaned.replace(/(?:\n\n|\n)?This analysis is for informational purposes only[\s\S]*$/i, '');
  cleaned = cleaned.replace(/(?:\n\n|\n)?Disclaimer:\s*[\s\S]*$/i, '');

  return cleaned.trim();
};

export const MessageItem: React.FC<MessageItemProps> = ({
  role,
  content,
  images,
  sources,
  agents_used,
  symbols_queried,
  context_truncated,
}) => {
  const isUser = role === 'user';
  const { user } = useAppStore();

  const getAvatarContent = () => {
    if (user?.avatar_url) {
      return <img src={user.avatar_url} alt="User" className="w-full h-full rounded-full object-cover" />;
    }
    if (user?.name) {
      const parts = user.name.split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return user.name.slice(0, 2).toUpperCase();
    }
    return 'GU';
  };

  // Clean inline citations like [1], [2], [source 3], raw debug chunk dumps, and trailing disclaimer blocks
  const cleanContent = isUser
    ? content
    : stripDisclaimersAndDebugTags(formatMarkdownTables(content.replace(/\[\d+\]|\[source\s*\d*\]/gi, '').trim()));

  // Extract synthesized opening takeaway if assistant message starts with text before headers
  let openingTakeaway = '';
  let mainBody = cleanContent;

  const isErrorMsg = cleanContent.includes('⚠️');

  if (!isUser && !isErrorMsg) {
    const headerMatch = cleanContent.search(/^#+\s+/m);
    if (headerMatch > 0) {
      openingTakeaway = cleanContent.slice(0, headerMatch).trim();
      mainBody = cleanContent.slice(headerMatch).trim();
    } else if (headerMatch === -1 && cleanContent.length > 0) {
      const firstParaEnd = cleanContent.indexOf('\n\n');
      if (firstParaEnd > 0) {
        openingTakeaway = cleanContent.slice(0, firstParaEnd).trim();
        mainBody = cleanContent.slice(firstParaEnd).trim();
      }
    }
  }

  return (
    <div className={`py-6 border-b border-border ${isUser ? 'bg-bg-primary' : 'bg-bg-secondary shadow-sm'}`}>
      <div className="max-w-4xl mx-auto px-4 md:px-8 flex space-x-5 min-w-0 w-full overflow-hidden">
        {/* Author Avatar */}
        <div className="flex-shrink-0 pt-0.5">
          {isUser ? (
            <div className="w-9 h-9 rounded-full bg-bg-tertiary border border-border flex items-center justify-center text-tx-secondary font-sans font-medium text-xs shadow-sm overflow-hidden">
              {getAvatarContent()}
            </div>
          ) : (
            <div className="w-9 h-9 rounded-full bg-accent-light border border-accent/20 flex items-center justify-center text-accent font-sans font-bold text-xs shadow-sm">
              AI
            </div>
          )}
        </div>

        {/* Message Content Container - Prevents horizontal overflow */}
        <div className="flex-1 space-y-4 min-w-0 overflow-hidden break-words">
          {/* Header Metadata (Agent Chips & Symbol Labels) */}
          <div className="flex flex-wrap items-center gap-2 text-[13px] text-tx-secondary">
            <span className="font-heading font-semibold text-tx-primary tracking-wide uppercase text-xs">{isUser ? 'You' : 'VittLens Analyst'}</span>

            {!isUser && agents_used && agents_used.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 ml-2">
                {agents_used.map((agent) => (
                  <AgentChip key={agent} name={agent} />
                ))}
              </div>
            )}

            {symbols_queried && symbols_queried.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 ml-2">
                {symbols_queried.map((sym) => (
                  <span key={sym} className="text-[11px] font-mono tabular-nums text-accent bg-accent-light px-2 py-0.5 rounded-md border border-accent/20">
                    ${sym}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Context Truncated Warning Banner */}
          {context_truncated && (
            <div className="alert-warm">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>Evidence ranked and compressed to fit token budget bounds.</span>
            </div>
          )}

          {/* Message Body */}
          {isUser ? (
            <p className="text-[15px] text-tx-primary whitespace-pre-wrap font-sans leading-relaxed break-words">{content}</p>
          ) : (
            <div className="space-y-5 min-w-0">
              {/* Synthesized 1-2 sentence takeaway in Fraunces font */}
              {openingTakeaway && (
                <div className="p-5 bg-bg-tertiary border-l-4 border-accent rounded-r-lg space-y-2 shadow-sm">
                  <div className="text-[11px] font-sans font-semibold tracking-widest text-tx-secondary uppercase">
                    KEY TAKEAWAY
                  </div>
                  <div className="ai-answer-serif text-lg text-tx-primary italic leading-relaxed">
                    {openingTakeaway}
                  </div>
                </div>
              )}

              {/* Restructured Main Answer Content */}
              <div className="ai-answer-serif text-[16px] space-y-4 min-w-0 break-words text-tx-primary leading-loose">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Sleek, interactive button links with Site Name & Globe icon
                    a: ({ href, children }) => {
                      if (!href) return <span>{children}</span>;
                      const siteName = getCleanSiteName(href, typeof children === 'string' ? children : undefined);
                      return (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center space-x-1.5 px-3 py-1 my-0.5 rounded-md bg-bg-tertiary border border-border hover:border-accent text-tx-primary hover:text-accent text-xs font-sans font-medium nav-transition shadow-sm group no-underline align-middle"
                        >
                          <Globe className="w-3.5 h-3.5 text-accent flex-shrink-0" />
                          <span className="truncate max-w-[180px]">{siteName}</span>
                          <ExternalLink className="w-3 h-3 text-tx-tertiary group-hover:text-accent flex-shrink-0" />
                        </a>
                      );
                    },
                    // Prominent, high-contrast cream headers
                    h1: ({ children }) => (
                      <h1 className="font-heading text-lg md:text-xl font-semibold tracking-wide text-tx-primary uppercase mt-8 mb-4 pb-2 border-b border-border flex items-center gap-2 select-none">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="font-heading text-base md:text-lg font-semibold tracking-wide text-tx-primary uppercase mt-8 mb-4 pb-2 border-b border-border flex items-center gap-2 select-none">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="font-heading text-sm md:text-base font-semibold tracking-wide text-tx-primary uppercase mt-6 mb-3 pb-1.5 border-b border-border flex items-center gap-2 select-none">
                        {children}
                      </h3>
                    ),
                    h4: ({ children }) => (
                      <h4 className="font-heading text-xs font-semibold tracking-wider text-tx-secondary uppercase mt-5 mb-2 select-none">
                        {children}
                      </h4>
                    ),
                    p: ({ children }) => (
                      <p className="text-[15px] text-tx-primary leading-relaxed my-3 break-words">
                        {React.Children.map(children, (child) =>
                          typeof child === 'string' ? renderTextWithTabularNums(child) : child
                        )}
                      </p>
                    ),
                    // Real Markdown Tables with columns and IBM Plex Mono tabular numbers
                    table: ({ children }) => (
                      <div className="overflow-x-auto max-w-full my-5 rounded-xl border border-border bg-bg-primary shadow-sm">
                        <table className="w-full text-left border-collapse text-sm font-sans">
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => (
                      <thead className="bg-bg-tertiary border-b border-border">
                        {children}
                      </thead>
                    ),
                    tr: ({ children }) => (
                      <tr className="border-b border-border hover:bg-bg-hover nav-transition">
                        {children}
                      </tr>
                    ),
                    th: ({ children }) => (
                      <th className="p-3 text-xs font-semibold tracking-wider text-tx-primary uppercase font-sans">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="p-3 text-tx-secondary font-mono tabular-nums text-sm">
                        {children}
                      </td>
                    ),
                    ul: ({ children }) => (
                      <ul className="space-y-2 my-4 pl-5 list-disc text-tx-primary font-sans text-[15px]">
                        {children}
                      </ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="space-y-2 my-4 pl-5 list-decimal text-tx-primary font-sans text-[15px]">
                        {children}
                      </ol>
                    ),
                    li: ({ children }) => (
                      <li className="leading-relaxed font-sans text-[15px] text-tx-primary break-words">
                        {React.Children.map(children, (child) =>
                          typeof child === 'string' ? renderTextWithTabularNums(child) : child
                        )}
                      </li>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-sans font-semibold text-tx-primary">
                        {children}
                      </strong>
                    ),
                    em: ({ children }) => (
                      <em className="ai-answer-serif italic text-tx-primary">
                        {children}
                      </em>
                    ),
                    code: ({ inline, className, children, ...props }: any) => {
                      const match = /language-(\w+)/.exec(className || '');
                      if (!inline && match && match[1] === 'chart') {
                        const symbol = String(children).replace(/\n$/, '').trim();
                        return <ChatChartBlock symbol={symbol} />;
                      }
                      return (
                        <code className="font-mono text-sm bg-bg-tertiary text-tx-primary border border-border px-2 py-0.5 rounded break-all" {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {mainBody}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Assistant Sub-components (Image Carousel & Sources Panel) */}
          {!isUser && (
            <div className="space-y-3 pt-2 min-w-0">
              <ImageCarousel images={images} />
              <SourcesPanel sources={sources} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
