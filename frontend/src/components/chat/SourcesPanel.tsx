import React, { useState } from 'react';
import { ChevronDown, ChevronRight, ExternalLink, FileText, Globe } from 'lucide-react';

interface SourcesPanelProps {
  sources?: string[];
}

/**
 * Clean URL site name parser.
 * Returns 'Google News' for Google News links, and clean domain names for external sites.
 */
export const getCleanSiteName = (url: string, defaultName?: string): string => {
  if (!url || typeof url !== 'string') return defaultName || 'Source';

  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./i, '').toLowerCase();

    // If URL is Google News, return 'Google News' as requested
    if (host.includes('google.com') || host.includes('news.google')) {
      return 'Google News';
    }

    // Clean domain for non-google sources (e.g. sec.gov -> SEC, bseindia.com -> Bseindia)
    let domain = host.replace(/\.(co|com|org|gov|net|edu)\.[a-z]{2,3}$/i, '');
    domain = domain.replace(/\.[a-z]{2,6}$/i, '');

    const parts = domain.split('.');
    const mainName = parts[parts.length - 1];
    const capitalized = mainName.charAt(0).toUpperCase() + mainName.slice(1).toLowerCase();

    return capitalized || 'Source';
  } catch (e) {
    return defaultName || 'Google News';
  }
};

export const SourcesPanel: React.FC<SourcesPanelProps> = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="pt-2 border-t border-hairline mt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-1.5 text-xs text-cream-muted hover:text-cream transition-colors font-sans font-normal py-1 select-none"
      >
        {isOpen ? (
          <ChevronDown className="w-3.5 h-3.5 text-cream-muted" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-cream-muted" />
        )}
        <span className="tracking-wide">
          {sources.length} Verified Source{sources.length > 1 ? 's' : ''}
        </span>
      </button>

      {isOpen && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {sources.map((src, idx) => {
            const isUrl = src.startsWith('http');
            const siteName = isUrl ? getCleanSiteName(src) : src;

            if (isUrl) {
              return (
                <a
                  key={idx}
                  href={src}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#14251B] border border-hairline hover:border-accent text-cream hover:text-accent text-xs font-sans font-medium transition-all shadow-sm group no-underline"
                >
                  <Globe className="w-3.5 h-3.5 text-accent flex-shrink-0" />
                  <span className="truncate max-w-[180px]">{siteName}</span>
                  <ExternalLink className="w-3 h-3 text-cream-muted group-hover:text-accent flex-shrink-0" />
                </a>
              );
            }

            return (
              <div
                key={idx}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#14251B] border border-hairline text-cream-muted text-xs font-sans"
              >
                <FileText className="w-3.5 h-3.5 text-cream-muted flex-shrink-0" />
                <span className="truncate max-w-[200px]">{src}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
