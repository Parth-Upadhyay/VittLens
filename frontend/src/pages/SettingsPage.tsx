import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { PreferencesService } from '../services/api';
import { Settings as SettingsIcon, Check, Info } from 'lucide-react';

const ANSWER_STYLES = [
  { id: 'Concise', title: 'Concise', desc: 'Direct, bulleted financial takeaways without preamble.' },
  { id: 'Detailed', title: 'Detailed', desc: 'Comprehensive financial breakdown with full evidence and ratio context.' },
  { id: 'Beginner', title: 'Beginner', desc: 'Simplified financial terms with plain-language explanations.' },
  { id: 'Expert', title: 'Expert', desc: 'Quantitative focus on SEC filings, valuation multiples, and cash flow.' },
];

export const SettingsPage: React.FC = () => {
  const { preferences, fetchPreferences } = useAppStore();
  const [style, setStyle] = useState(preferences.answer_style || 'Detailed');
  const [symbols, setSymbols] = useState(preferences.default_symbols?.join(', ') || 'RELIANCE, TCS, INFY');
  const [theme, setTheme] = useState(preferences.theme || 'Dark');
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    setStyle(preferences.answer_style || 'Detailed');
    setSymbols(preferences.default_symbols?.join(', ') || 'RELIANCE, TCS, INFY');
    setTheme(preferences.theme || 'Dark');
  }, [preferences]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const symList = symbols.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);

    try {
      await PreferencesService.updatePreferences({
        answer_style: style as any,
        default_symbols: symList,
        theme: theme as any,
      });
      await fetchPreferences();
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2000);
    } catch (e) {
      console.error('Failed to save preferences:', e);
    }
  };

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">
      {/* Professional Title Bar without Emojis or Bounding Box */}
      <div className="flex items-center space-x-2.5 pb-2">
        <SettingsIcon className="w-5 h-5 text-accent" />
        <h1 className="text-xl font-medium text-cream tracking-tight">Preferences & Configuration</h1>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Answer Style Radio Cards */}
        <div className="space-y-3">
          <label className="text-xs font-medium text-cream-muted uppercase tracking-wider">AI Answer Persona Style</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {ANSWER_STYLES.map((st) => {
              const active = style === st.id;
              return (
                <div
                  key={st.id}
                  onClick={() => setStyle(st.id as any)}
                  className={`p-4 rounded-xl border cursor-pointer transition-colors space-y-1 ${
                    active
                      ? 'border-accent bg-[#14251B] text-cream font-medium shadow-sm'
                      : 'border-hairline bg-[#0D1912] text-cream-muted hover:bg-[#14251B]/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-cream">{st.title}</span>
                    {active && <Check className="w-4 h-4 text-accent" />}
                  </div>
                  <p className="text-xs text-cream-muted leading-relaxed">{st.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Quick Access Symbols with Clear Explanation */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-cream-muted uppercase tracking-wider">Quick-Access Symbol Chips</label>
          </div>

          <div className="flex items-start space-x-2 p-3 bg-[#0D1912] border border-hairline rounded-lg text-xs text-cream-muted">
            <Info className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              These stock symbols appear as interactive one-click shortcut buttons directly above the chat composer input box (e.g. RELIANCE, TCS, INFY). Clicking any chip quickly inserts or compares that stock in your chat prompt.
            </p>
          </div>

          <input
            type="text"
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            placeholder="Comma separated symbols (e.g. RELIANCE, TCS, INFY, HDFCBANK)"
            className="w-full bg-[#0D1912] border border-hairline text-xs text-cream placeholder-cream-dim rounded-lg px-3 py-2 focus:outline-none focus:border-accent font-sans"
          />
        </div>

        {/* Theme Selector */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-cream-muted uppercase tracking-wider">UI Appearance Theme</label>
          <div className="flex space-x-3">
            {['Dark', 'Light', 'System'].map((th) => (
              <button
                type="button"
                key={th}
                onClick={() => setTheme(th as any)}
                className={`px-4 py-2 rounded-lg border text-xs font-medium transition-colors ${
                  theme === th
                    ? 'border-accent bg-[#14251B] text-cream font-medium shadow-sm'
                    : 'border-hairline bg-[#0D1912] text-cream-muted hover:text-cream'
                }`}
              >
                {th}
              </button>
            ))}
          </div>
        </div>

        {/* Save Button */}
        <div className="pt-4 flex items-center space-x-3">
          <button
            type="submit"
            className="bg-accent hover:bg-accent-hover text-cream text-xs font-medium px-5 py-2.5 rounded-lg transition-colors shadow-sm"
          >
            Save Settings
          </button>
          {isSaved && <span className="text-xs text-semantic-green font-medium font-sans">Settings saved!</span>}
        </div>
      </form>
    </div>
  );
};
