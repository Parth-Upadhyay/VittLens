import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, AlertTriangle, ExternalLink, Globe } from 'lucide-react';
import { ImageCarousel } from './ImageCarousel';
import { SourcesPanel, getCleanSiteName } from './SourcesPanel';
import { AgentChip } from './AgentChip';

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
        <span key={i} className="font-mono tabular-nums text-cream font-medium">
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

  // Clean inline citations like [1], [2], [source 3], raw debug chunk dumps, and trailing disclaimer blocks
  const cleanContent = isUser
    ? content
    : stripDisclaimersAndDebugTags(formatMarkdownTables(content.replace(/\[\d+\]|\[source\s*\d*\]/gi, '').trim()));

  // Extract synthesized opening takeaway if assistant message starts with text before headers
  let openingTakeaway = '';
  let mainBody = cleanContent;

  if (!isUser) {
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
    <div className={`py-5 border-b border-hairline ${isUser ? 'bg-[#060E0A]' : 'bg-[#0D1912]'}`}>
      <div className="max-w-4xl mx-auto px-4 flex space-x-4 min-w-0 w-full overflow-hidden">
        {/* Author Avatar */}
        <div className="flex-shrink-0 pt-0.5">
          {isUser ? (
            <div className="w-8 h-8 rounded-full bg-[#14251B] border border-hairline flex items-center justify-center text-cream-muted font-sans text-xs">
              <User className="w-4 h-4" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-[#14251B] border border-hairline flex items-center justify-center text-accent font-sans font-medium text-xs">
              AI
            </div>
          )}
        </div>

        {/* Message Content Container - Prevents horizontal overflow */}
        <div className="flex-1 space-y-3 min-w-0 overflow-hidden break-words">
          {/* Header Metadata (Agent Chips & Symbol Labels) */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-cream-muted">
            <span className="font-sans font-medium text-cream">{isUser ? 'You' : 'VittLens Analyst'}</span>

            {!isUser && agents_used && agents_used.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 ml-1">
                {agents_used.map((agent) => (
                  <AgentChip key={agent} name={agent} />
                ))}
              </div>
            )}

            {symbols_queried && symbols_queried.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 ml-1">
                {symbols_queried.map((sym) => (
                  <span key={sym} className="text-[10px] font-mono tabular-nums text-accent bg-accent/15 px-1.5 py-0.5 rounded border border-accent/30">
                    ${sym}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Context Truncated Warning Banner */}
          {context_truncated && (
            <div className="flex items-center space-x-2 p-2.5 rounded bg-semantic-amber/10 border border-semantic-amber/30 text-semantic-amber text-xs font-sans">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>Evidence ranked and compressed to fit token budget bounds.</span>
            </div>
          )}

          {/* Message Body */}
          {isUser ? (
            <p className="text-sm text-cream whitespace-pre-wrap font-sans leading-relaxed break-words">{content}</p>
          ) : (
            <div className="space-y-4 min-w-0">
              {/* Synthesized 1-2 sentence takeaway in Fraunces font */}
              {openingTakeaway && (
                <div className="p-4 bg-[#14251B]/60 border-l-2 border-accent rounded-r space-y-1.5 shadow-sm">
                  <div className="text-[10px] font-sans font-medium tracking-widest text-cream-muted uppercase">
                    KEY TAKEAWAY
                  </div>
                  <div className="ai-answer-serif text-base text-cream italic leading-relaxed">
                    {openingTakeaway}
                  </div>
                </div>
              )}

              {/* Restructured Main Answer Content */}
              <div className="ai-answer-serif text-base space-y-4 min-w-0 break-words">
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
                          className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 my-0.5 rounded bg-[#14251B] border border-hairline hover:border-accent text-cream hover:text-accent text-xs font-sans font-medium transition-all shadow-sm group no-underline align-middle"
                        >
                          <Globe className="w-3.5 h-3.5 text-accent flex-shrink-0" />
                          <span className="truncate max-w-[180px]">{siteName}</span>
                          <ExternalLink className="w-3 h-3 text-cream-muted group-hover:text-accent flex-shrink-0" />
                        </a>
                      );
                    },
                    // Prominent, high-contrast cream headers
                    h1: ({ children }) => (
                      <h1 className="font-sans text-sm md:text-base font-medium tracking-wide text-cream uppercase mt-6 mb-3 pb-1.5 border-b border-hairline flex items-center gap-2 select-none">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="font-sans text-sm md:text-base font-medium tracking-wide text-cream uppercase mt-6 mb-3 pb-1.5 border-b border-hairline flex items-center gap-2 select-none">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="font-sans text-xs md:text-sm font-medium tracking-wide text-cream uppercase mt-5 mb-2.5 pb-1 border-b border-hairline/80 flex items-center gap-2 select-none">
                        {children}
                      </h3>
                    ),
                    h4: ({ children }) => (
                      <h4 className="font-sans text-xs font-medium tracking-wider text-cream-muted uppercase mt-4 mb-2 select-none">
                        {children}
                      </h4>
                    ),
                    p: ({ children }) => (
                      <p className="text-sm text-cream leading-relaxed my-2 break-words">
                        {React.Children.map(children, (child) =>
                          typeof child === 'string' ? renderTextWithTabularNums(child) : child
                        )}
                      </p>
                    ),
                    // Real Markdown Tables with columns and IBM Plex Mono tabular numbers
                    table: ({ children }) => (
                      <div className="overflow-x-auto max-w-full my-4 rounded-lg border border-hairline bg-[#060E0A] shadow-sm">
                        <table className="w-full text-left border-collapse text-xs font-sans">
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => (
                      <thead className="bg-[#14251B] border-b border-hairline">
                        {children}
                      </thead>
                    ),
                    tr: ({ children }) => (
                      <tr className="border-b border-hairline/40 hover:bg-[#14251B]/40 transition-colors">
                        {children}
                      </tr>
                    ),
                    th: ({ children }) => (
                      <th className="p-2.5 text-[11px] font-medium tracking-wider text-cream uppercase font-sans">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="p-2.5 text-cream-muted font-mono tabular-nums text-xs">
                        {children}
                      </td>
                    ),
                    ul: ({ children }) => (
                      <ul className="space-y-1.5 my-3 pl-4 list-disc text-cream font-sans text-sm">
                        {children}
                      </ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="space-y-1.5 my-3 pl-4 list-decimal text-cream font-sans text-sm">
                        {children}
                      </ol>
                    ),
                    li: ({ children }) => (
                      <li className="leading-relaxed font-sans text-sm text-cream break-words">
                        {React.Children.map(children, (child) =>
                          typeof child === 'string' ? renderTextWithTabularNums(child) : child
                        )}
                      </li>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-sans font-medium text-cream">
                        {children}
                      </strong>
                    ),
                    em: ({ children }) => (
                      <em className="ai-answer-serif italic text-cream">
                        {children}
                      </em>
                    ),
                    code: ({ children }) => (
                      <code className="font-mono text-xs bg-[#14251B] text-cream border border-hairline px-1.5 py-0.5 rounded break-all">
                        {children}
                      </code>
                    ),
                  }}
                >
                  {mainBody}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Assistant Sub-components (Image Carousel & Sources Panel) */}
          {!isUser && (
            <div className="space-y-2 pt-1 min-w-0">
              <ImageCarousel images={images} />
              <SourcesPanel sources={sources} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
