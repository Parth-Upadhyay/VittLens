import React, { useState, useRef } from 'react';
import { Send, AtSign, Loader2 } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

interface ChatComposerProps {
  onSend: (question: string) => void;
  isLoading: boolean;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({ onSend, isLoading }) => {
  const [text, setText] = useState('');
  const [showMentionDropdown, setShowMentionDropdown] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { preferences, marketSymbols, queriesRemaining, guestSession } = useAppStore();

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
    
    if (lastAtIdx !== -1) {
      const newText = textBeforeCursor.slice(0, lastAtIdx) + `@${symbol} ` + text.slice(cursor);
      setText(newText);
      setShowMentionDropdown(false);
    }
    textareaRef.current.focus();
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSend(text.trim());
    setText('');
    setShowMentionDropdown(false);
  };

  const allSymbols = Object.keys(marketSymbols);
  const filteredSymbols = allSymbols
    .filter((s) => s.includes(mentionFilter))
    .slice(0, 20); // Cap at 20 for UI performance

  return (
    <div className="relative max-w-4xl mx-auto px-2 md:px-8 pt-2 md:pt-4 pb-4 md:pb-6 w-full bg-bg-primary">
      {/* Quick-Access Symbol Chips */}
      {preferences.default_symbols && preferences.default_symbols.length > 0 && (
        <div className="flex items-center space-x-2 mb-3 overflow-x-auto text-xs text-tx-secondary no-scrollbar">
          <span className="text-[11px] text-tx-tertiary font-medium">Quick:</span>
          {preferences.default_symbols.map((sym) => (
            <button
              key={sym}
              onClick={() => setText((prev) => (prev ? `${prev} ${sym}` : `Compare ${sym}`))}
              className="px-2.5 py-1 rounded-md bg-bg-tertiary border border-border text-tx-secondary hover:text-tx-primary hover:border-accent nav-transition font-medium shadow-sm"
            >
              {sym}
            </button>
          ))}
        </div>
      )}

      {/* Autocomplete Dropdown */}
      {showMentionDropdown && filteredSymbols.length > 0 && (
        <div className="absolute bottom-full mb-3 left-4 md:left-8 z-30 w-64 bg-bg-secondary border border-border rounded-xl shadow-xl max-h-56 overflow-y-auto p-1.5 space-y-0.5">
          <div className="px-3 py-1.5 text-[10px] text-tx-tertiary font-mono tracking-wider font-semibold">MARKET SYMBOLS</div>
          {filteredSymbols.map((sym) => (
            <button
              key={sym}
              onClick={() => handleSelectMention(sym)}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-tx-primary hover:bg-bg-hover hover:text-accent nav-transition flex items-center justify-between"
            >
              <span className="font-mono font-medium">{sym}</span>
              <AtSign className="w-3.5 h-3.5 text-tx-tertiary" />
            </button>
          ))}
        </div>
      )}

      {/* Main Composer Input Card */}
      <form onSubmit={handleSubmit} className="bg-bg-secondary border border-border rounded-2xl p-2.5 flex items-end space-x-3 shadow-md focus-within:border-accent focus-within:shadow-lg transition-all duration-200">
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
          className="flex-1 bg-transparent border-0 text-[15px] text-tx-primary placeholder-tx-tertiary focus:outline-none resize-none min-h-[44px] max-h-40 p-2 disabled:opacity-50 font-sans"
          rows={1}
        />

        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          className={`p-3 rounded-xl transition-all flex-shrink-0 flex items-center justify-center btn-press shadow-sm ${
            text.trim() && !isLoading
              ? 'bg-accent hover:bg-accent-hover text-white'
              : 'bg-bg-tertiary text-tx-tertiary cursor-not-allowed border border-border'
          }`}
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-accent" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </form>

      {/* Persistent SEBI Disclaimer Notice Line */}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex-1"></div>
        <div className="text-[11px] text-tx-tertiary text-center font-sans tracking-wide font-medium flex-1">
          SEBI Disclaimer: VittLens is an AI analytical tool for educational purposes only and not a SEBI-registered advisor.
        </div>
        <div className="flex-1 flex justify-end">
          {guestSession && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-bg-tertiary border border-border text-tx-secondary">
              Guest Queries: {queriesRemaining >= 0 ? queriesRemaining : 15} left
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
