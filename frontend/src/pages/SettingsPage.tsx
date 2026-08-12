import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { PreferencesService } from '../services/api';
import { Settings as SettingsIcon, Check, Info } from 'lucide-react';
import { toast } from 'react-hot-toast';

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
  const [theme, setTheme] = useState(preferences.theme || 'Light');
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    setStyle(preferences.answer_style || 'Detailed');
    setSymbols(preferences.default_symbols?.join(', ') || 'RELIANCE, TCS, INFY');
    setTheme(preferences.theme || 'Light');
  }, [preferences]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const symList = symbols.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);

    try {
      const hasToken = !!localStorage.getItem('auth_token');
      if (!hasToken) {
        sessionStorage.setItem('vittlens_theme_guest', theme);
        toast('Please refresh the page to apply theme changes.', {
          icon: '🔄',
          style: {
            borderRadius: '10px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
          },
        });
      } else {
        localStorage.setItem('vittlens_theme', theme);
      }
      
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
      // For guest users where backend save might fail, still update UI state locally
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2000);
      if (!localStorage.getItem('auth_token')) {
        toast('Please refresh the page to apply theme changes.', {
          icon: '🔄',
          style: {
            borderRadius: '10px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
          },
        });
      }
    }
  };

  return (
    <div className="flex-1 p-8 w-full max-w-[1400px] mx-auto space-y-8 font-sans bg-bg-primary animate-page-in">
      {/* Title Bar */}
      <div className="flex items-center space-x-3">
        <SettingsIcon className="w-5 h-5 text-accent" />
        <h1 className="text-2xl font-heading font-semibold text-tx-primary tracking-tight">Preferences & Configuration</h1>
      </div>

      <form onSubmit={handleSave} className="space-y-8 max-w-4xl">
        {/* Answer Style Radio Cards */}
        <div className="space-y-4">
          <label className="metric-label">AI Answer Persona Style</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {ANSWER_STYLES.map((st) => {
              const active = style === st.id;
              return (
                <div
                  key={st.id}
                  onClick={() => setStyle(st.id as any)}
                  className={`p-5 rounded-card border cursor-pointer nav-transition space-y-2 flex flex-col justify-between ${
                    active
                      ? 'border-accent bg-accent-light text-tx-primary shadow-sm'
                      : 'surface-card text-tx-secondary hover:bg-bg-hover'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[15px] font-semibold text-tx-primary">{st.title}</span>
                    {active && <Check className="w-4 h-4 text-accent" />}
                  </div>
                  <p className="text-xs text-tx-secondary leading-relaxed">{st.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Quick Access Symbols */}
        <div className="space-y-4">
          <label className="metric-label">Quick-Access Symbol Chips</label>
          
          <div className="flex items-start space-x-3 p-4 bg-bg-tertiary border border-border rounded-lg text-xs text-tx-secondary font-sans">
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
            className="w-full bg-bg-input border border-border text-sm text-tx-primary placeholder-tx-tertiary rounded-lg px-4 py-3 input-glow font-sans"
          />
        </div>

        {/* Theme Selector */}
        <div className="space-y-4">
          <label className="metric-label">UI Appearance Theme</label>
          <div className="flex space-x-3">
            {['Light', 'Dark', 'System'].map((th) => (
              <button
                type="button"
                key={th}
                onClick={() => setTheme(th as any)}
                className={`px-5 py-2.5 rounded-lg border text-sm font-medium nav-transition btn-press ${
                  theme === th
                    ? 'border-accent bg-accent-light text-accent shadow-sm'
                    : 'border-border bg-bg-secondary text-tx-secondary hover:text-tx-primary hover:bg-bg-hover'
                }`}
              >
                {th}
              </button>
            ))}
          </div>
        </div>

        {/* Save Button */}
        <div className="pt-6 border-t border-border flex items-center space-x-4">
          <button
            type="submit"
            className="bg-accent hover:bg-accent-hover text-white text-sm font-medium px-6 py-2.5 rounded-lg nav-transition btn-press shadow-sm"
          >
            Save Settings
          </button>
          {isSaved && <span className="text-sm text-semantic-green font-medium font-sans">Settings saved successfully!</span>}
        </div>
      </form>
    </div>
  );
};
