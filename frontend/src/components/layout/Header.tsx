import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/useAppStore';
import { LogIn, Sparkles, Menu, User as UserIcon, ShieldAlert, X, Building2, ExternalLink, CheckCircle2 } from 'lucide-react';

interface HeaderProps {
  onToggleSidebar: () => void;
}

const AVAILABLE_COMPANIES = [
  { symbol: 'RELIANCE', name: 'Reliance Industries Ltd.', sector: 'Energy & Retail', yfinance: 'RELIANCE.NS' },
  { symbol: 'TCS', name: 'Tata Consultancy Services Ltd.', sector: 'IT Services', yfinance: 'TCS.NS' },
  { symbol: 'HDFCBANK', name: 'HDFC Bank Ltd.', sector: 'Banking', yfinance: 'HDFCBANK.NS' },
  { symbol: 'ICICIBANK', name: 'ICICI Bank Ltd.', sector: 'Banking', yfinance: 'ICICIBANK.NS' },
  { symbol: 'INFY', name: 'Infosys Ltd.', sector: 'IT Services', yfinance: 'INFY.NS' },
  { symbol: 'BHARTIARTL', name: 'Bharti Airtel Ltd.', sector: 'Telecom', yfinance: 'BHARTIARTL.NS' },
  { symbol: 'ITC', name: 'ITC Ltd.', sector: 'FMCG / Diversified', yfinance: 'ITC.NS' },
  { symbol: 'SBIN', name: 'State Bank of India', sector: 'Banking', yfinance: 'SBIN.NS' },
  { symbol: 'LT', name: 'Larsen & Toubro Ltd.', sector: 'Engineering & Infrastructure', yfinance: 'LT.NS' },
  { symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank Ltd.', sector: 'Banking', yfinance: 'KOTAKBANK.NS' },
  { symbol: 'AXISBANK', name: 'Axis Bank Ltd.', sector: 'Banking', yfinance: 'AXISBANK.NS' },
  { symbol: 'HCLTECH', name: 'HCL Technologies Ltd.', sector: 'IT Services', yfinance: 'HCLTECH.NS' },
  { symbol: 'ASIANPAINT', name: 'Asian Paints Ltd.', sector: 'Paints & Building', yfinance: 'ASIANPAINT.NS' },
  { symbol: 'MARUTI', name: 'Maruti Suzuki India Ltd.', sector: 'Automobile', yfinance: 'MARUTI.NS' },
  { symbol: 'SUNPHARMA', name: 'Sun Pharmaceutical Industries Ltd.', sector: 'Pharmaceuticals', yfinance: 'SUNPHARMA.NS' },
  { symbol: 'TITAN', name: 'Titan Company Ltd.', sector: 'Consumer Goods', yfinance: 'TITAN.NS' },
  { symbol: 'BAJFINANCE', name: 'Bajaj Finance Ltd.', sector: 'Financial Services', yfinance: 'BAJFINANCE.NS' },
  { symbol: 'ULTRACEMCO', name: 'UltraTech Cement Ltd.', sector: 'Cement & Building', yfinance: 'ULTRACEMCO.NS' },
  { symbol: 'NTPC', name: 'NTPC Ltd.', sector: 'Power Generation', yfinance: 'NTPC.NS' },
];

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { user, queriesRemaining, setGuestLimitModalOpen, logout } = useAppStore();
  const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
  const [isCompaniesModalOpen, setIsCompaniesModalOpen] = useState(false);
  const navigate = useNavigate();

  const handleGoogleLogin = () => {
    window.location.href = '/api/v1/auth/google/login';
  };

  const handleCompanyClick = (symbol: string) => {
    setIsCompaniesModalOpen(false);
    navigate(`/company/${symbol}`);
  };

  return (
    <>
      <header className="h-14 bg-[#0D1912] border-b border-hairline flex items-center justify-between px-4 sticky top-0 z-30 font-sans flex-shrink-0 select-none">
        {/* Left Branding & Sidebar Toggle */}
        <div className="flex items-center space-x-3">
          <button
            onClick={onToggleSidebar}
            className="p-1.5 rounded-lg text-cream-muted hover:text-cream hover:bg-[#14251B] transition-colors"
            aria-label="Toggle Navigation Sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>

          <Link to="/chat" className="flex items-center space-x-2">
            <span className="text-base font-medium tracking-tight text-cream">Vitt<span className="text-accent">Lens</span></span>
            <span className="text-[10px] text-cream-muted border border-hairline px-1.5 py-0.5 rounded font-mono tabular-nums bg-[#14251B]">NIFTY 20</span>
          </Link>

          {/* SEBI Legal Disclaimer Badge */}
          <button
            onClick={() => setIsDisclaimerOpen(true)}
            className="hidden md:flex items-center space-x-1.5 px-2 py-0.5 rounded-full text-[11px] text-cream-dim hover:text-cream bg-[#14251B] border border-hairline hover:border-accent/40 transition-colors ml-2"
            title="Click to view legally binding SEBI Legal Disclaimer"
          >
            <ShieldAlert className="w-3 h-3 text-accent" />
            <span>SEBI Disclaimer</span>
          </button>
        </div>

        {/* Right Controls */}
        <div className="flex items-center space-x-2">
          {/* Available Companies Button */}
          <button
            onClick={() => setIsCompaniesModalOpen(true)}
            className="flex items-center space-x-1.5 bg-[#14251B] hover:bg-[#1B3124] text-cream border border-hairline hover:border-accent/60 text-xs px-2.5 py-1 rounded-md transition-colors"
            title="View 20 available NIFTY companies"
          >
            <Building2 className="w-3.5 h-3.5 text-accent" />
            <span className="hidden sm:inline">Coverage</span>
            <span className="sm:hidden">20</span>
          </button>

          {/* Guest Query Counter Badge */}
          {!user && (
            <button
              onClick={() => queriesRemaining === 0 && setGuestLimitModalOpen(true)}
              className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs transition-colors ${
                queriesRemaining === 0
                  ? 'border border-semantic-red/40 bg-semantic-red/10 text-semantic-red font-mono'
                  : 'border border-hairline bg-[#14251B] text-cream-muted font-mono'
              }`}
            >
              <Sparkles className="w-3 h-3 text-accent" />
              <span>{queriesRemaining < 0 ? '∞' : `${queriesRemaining}/3`}</span>
            </button>
          )}

          {/* User Account / OAuth Login Button */}
          {user ? (
            <div className="flex items-center space-x-2">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.name || 'User'} className="w-6 h-6 rounded-full border border-hairline" />
              ) : (
                <div className="w-6 h-6 rounded-full bg-[#14251B] border border-hairline text-accent flex items-center justify-center text-[10px] font-medium">
                  {user.name ? user.name[0].toUpperCase() : <UserIcon className="w-3.5 h-3.5" />}
                </div>
              )}
              <button
                onClick={logout}
                className="text-xs text-cream-muted hover:text-cream transition-colors"
              >
                Exit
              </button>
            </div>
          ) : (
            <button
              onClick={handleGoogleLogin}
              className="flex items-center space-x-1.5 bg-accent hover:bg-accent-hover text-cream text-xs font-medium px-2.5 py-1 rounded-md transition-colors shadow-sm"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span className="hidden xs:inline">Sign In</span>
            </button>
          )}
        </div>
      </header>

      {/* Available Companies Modal */}
      {isCompaniesModalOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D1912] border border-hairline rounded-xl max-w-3xl w-full p-6 space-y-5 shadow-2xl relative max-h-[85vh] flex flex-col">
            <button
              onClick={() => setIsCompaniesModalOpen(false)}
              className="absolute top-4 right-4 p-1 text-cream-muted hover:text-cream"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2.5">
              <div className="p-2 rounded-lg bg-accent/15 border border-accent/30 text-accent">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-medium text-cream">Available NIFTY 20 Data Index</h2>
                <p className="text-xs text-cream-muted">Real-time quotes, ratio profiles, annual filings, and live news timelines for 20 companies.</p>
              </div>
            </div>

            {/* Grid of Available Companies */}
            <div className="overflow-y-auto pr-1 space-y-3 flex-1 scrollbar-thin">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {AVAILABLE_COMPANIES.map((comp) => (
                  <div
                    key={comp.symbol}
                    onClick={() => handleCompanyClick(comp.symbol)}
                    className="p-3 rounded-lg bg-[#14251B] border border-hairline hover:border-accent transition-all cursor-pointer group flex items-center justify-between"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-medium text-accent bg-accent/15 px-1.5 py-0.5 rounded border border-accent/30">
                          ${comp.symbol}
                        </span>
                        <span className="text-xs font-medium text-cream group-hover:text-accent transition-colors truncate max-w-[170px]">
                          {comp.name}
                        </span>
                      </div>
                      <div className="text-[11px] text-cream-muted flex items-center space-x-2 font-sans">
                        <span>{comp.sector}</span>
                        <span>•</span>
                        <span className="font-mono text-[10px] text-cream-dim">{comp.yfinance}</span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-1 text-[10px] text-semantic-green bg-semantic-green/10 border border-semantic-green/30 px-2 py-1 rounded-full flex-shrink-0">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Ready</span>
                      <ExternalLink className="w-3 h-3 ml-1 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-hairline flex items-center justify-between text-xs text-cream-muted font-sans">
              <span>20/20 NIFTY Benchmark Companies Active</span>
              <button
                onClick={() => setIsCompaniesModalOpen(false)}
                className="bg-[#14251B] hover:bg-[#1B3124] text-cream border border-hairline px-4 py-1.5 rounded-lg transition-colors"
              >
                Close Index
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Legally Binding SEBI Legal Disclaimer Modal */}
      {isDisclaimerOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D1912] border border-hairline rounded-xl max-w-lg w-full p-6 space-y-4 shadow-2xl relative">
            <button
              onClick={() => setIsDisclaimerOpen(false)}
              className="absolute top-4 right-4 p-1 text-cream-muted hover:text-cream"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-5 h-5 text-accent" />
              <h2 className="text-base font-medium text-cream">SEBI Statutory Legal Disclaimer (India)</h2>
            </div>

            <div className="space-y-3 text-xs text-cream-muted leading-relaxed font-sans border-t border-hairline pt-3">
              <p>
                <strong className="text-cream">1. Educational & Information Purpose Only:</strong> VittLens is an automated artificial intelligence analytical tool designed solely for informational, research, and educational purposes.
                The reports, valuation metrics, sentiment analyses, and quantitative scores generated by this system do <strong>NOT</strong> constitute financial advice, investment recommendations, endorsement, or solicitation to buy or sell any security.
                <br /><br />
                <strong className="text-cream">2. SEBI Non-Registration Notice:</strong> VittLens is <strong className="text-cream">NOT</strong> a SEBI-registered Investment Adviser (IA) under the SEBI (Investment Advisers) Regulations, 2013, nor a SEBI-registered Research Analyst (RA) under the SEBI (Research Analysts) Regulations, 2014.
              </p>
              <p>
                <strong className="text-cream">3. No Financial Advice or Recommendations:</strong> No content, ratio snapshot, filing summary, or generated output provided on this platform constitutes investment advice, stock tips, buy/sell recommendations, or financial endorsement.
              </p>
              <p>
                <strong className="text-cream">4. User Responsibility:</strong> Indian equity investments involve market risks. Users are strictly advised to verify data independently and consult certified SEBI-registered financial advisors before making investment decisions.
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setIsDisclaimerOpen(false)}
                className="bg-accent hover:bg-accent-hover text-cream text-xs font-medium px-4 py-2 rounded-lg transition-colors"
              >
                I Understand
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
