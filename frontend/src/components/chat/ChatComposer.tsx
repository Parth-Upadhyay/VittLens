import React, { useState, useRef } from 'react';
import { Send, AtSign, Loader2 } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

const NIFTY20_SYMBOLS = [
  'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',
  'BHARTIARTL', 'SBIN', 'ITC', 'HCLTECH',
  'BAJFINANCE', 'LT', 'MARUTI', 'AXISBANK', 'KOTAKBANK',
  'SUNPHARMA', 'TITAN', 'ULTRACEMCO', 'TATASTEEL', 'NTPC'
];

interface ChatComposerProps {
  onSend: (question: string) => void;
  isLoading: boolean;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({ onSend, isLoading }) => {
  const [text, setText] = useState('');
  const [showMentionDropdown, setShowMentionDropdown] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { preferences } = useAppStore();

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);

    // Check for @ mention trigger
    const cursor = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursor);
    const lastAtIdx = textBeforeCursor.lastIndexOf('@');

    if (lastAtIdx !== -1 && !textBeforeCursor.slice(lastAtIdx).includes(' ')) {
      setShowMentionDropdown(true);
      setMentionFilter(textBeforeCursor.slice(lastAtIdx + 1).toUpperCase());
    } else {
      setShowMentionDropdown(false);
    }
  };

  const handleSelectMention = (symbol: string) => {
    if (!textareaRef.current) return;
    const cursor = textareaRef.current.selectionStart;
    const textBeforeCursor = text.slice(0, cursor);
    const lastAtIdx = textBeforeCursor.lastIndexOf('@');

    const newText = text.slice(0, lastAtIdx) + `@${symbol} ` + text.slice(cursor);
    setText(newText);
    setShowMentionDropdown(false);
    textareaRef.current.focus();
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSend(text.trim());
    setText('');
    setShowMentionDropdown(false);
  };

  const filteredSymbols = NIFTY20_SYMBOLS.filter((s) => s.includes(mentionFilter));

  return (
    <div className="relative max-w-4xl mx-auto px-4 pt-4 pb-5 w-full">
      {/* Quick-Access Symbol Chips */}
      {preferences.default_symbols && preferences.default_symbols.length > 0 && (
        <div className="flex items-center space-x-1.5 mb-3 overflow-x-auto text-xs text-cream-muted">
          <span className="text-[11px] text-cream-dim">Quick:</span>
          {preferences.default_symbols.map((sym) => (
            <button
              key={sym}
              onClick={() => setText((prev) => (prev ? `${prev} ${sym}` : `Compare ${sym}`))}
              className="px-2 py-0.5 rounded bg-[#0D1912] border border-hairline text-cream-muted hover:text-cream hover:border-accent transition-colors"
            >
              {sym}
            </button>
          ))}
        </div>
      )}

      {/* Autocomplete Dropdown */}
      {showMentionDropdown && filteredSymbols.length > 0 && (
        <div className="absolute bottom-full mb-2 left-4 z-30 w-64 bg-[#14251B] border border-hairline rounded-lg shadow-xl max-h-48 overflow-y-auto p-1 space-y-0.5">
          <div className="px-2 py-1 text-[10px] text-cream-dim font-mono">NIFTY 20 SYMBOLS</div>
          {filteredSymbols.map((sym) => (
            <button
              key={sym}
              onClick={() => handleSelectMention(sym)}
              className="w-full text-left px-2.5 py-1.5 rounded text-xs text-cream hover:bg-[#0D1912] hover:text-accent transition-colors flex items-center justify-between"
            >
              <span className="font-mono font-medium">{sym}</span>
              <AtSign className="w-3 h-3 text-cream-dim" />
            </button>
          ))}
        </div>
      )}

      {/* Main Composer Input Card */}
      <form onSubmit={handleSubmit} className="bg-[#0D1912] border border-hairline rounded-xl p-2 flex items-end space-x-2 shadow-lg focus-within:border-accent/80 transition-colors">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleTextChange}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          disabled={isLoading}
          placeholder={isLoading ? "Agents processing query... Please wait..." : "Ask a financial question... (type @ for NIFTY 20 autocomplete)"}
          className="flex-1 bg-transparent border-0 text-sm text-cream placeholder-cream-dim focus:outline-none resize-none min-h-[44px] max-h-32 p-2 disabled:opacity-50 font-sans"
          rows={1}
        />

        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          className={`p-2.5 rounded-lg transition-colors flex-shrink-0 flex items-center justify-center ${
            text.trim() && !isLoading
              ? 'bg-accent hover:bg-accent-hover text-cream'
              : 'bg-[#14251B] text-cream-dim cursor-not-allowed'
          }`}
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin text-accent" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </form>

      {/* Persistent SEBI Disclaimer Notice Line */}
      <div className="mt-2 text-[10px] text-cream-dim text-center font-sans tracking-wide">
        SEBI Disclaimer: FinnAI is an AI analytical tool for educational purposes only and not a SEBI-registered advisor.
      </div>
    </div>
  );
};
