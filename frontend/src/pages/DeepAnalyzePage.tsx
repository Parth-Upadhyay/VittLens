import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Microscope, Search, ChevronDown, ChevronUp, AlertTriangle, Lightbulb, Activity, TrendingUp, Shield, BarChart3 } from 'lucide-react';
import { MarketService } from '../services/api';
import { SymbolSearch } from '../components/common/SymbolSearch';

interface Metric {
  category: string;
  key: string;
  label: string;
  value: number | string;
  unit: string;
  format_rule: string;
  source?: string;
}

interface DeepAnalysisMetric {
  metric: string;
  value: string;
  interpretation: string;
}

interface AgentData {
  company: string;
  current: { price: number; currency: string; marketCap?: number; dayHigh?: number; dayLow?: number; timestamp: string };
  valuation: { forwardPE?: number; trailingPE?: number; priceToBook?: number; enterpriseValue?: number };
  financials: { year: number; revenue?: number; netIncome?: number; eps?: number; operatingMargin?: number }[];
  health: { totalDebt?: number; cash?: number; netDebt?: number; debtToEquity?: number; currentRatio?: number };
}

interface DeepData {
  symbol: string;
  ticker: string;
  metrics: Metric[];
  overall_assessment: string;
  deep_analysis: {
    business_quality?: DeepAnalysisMetric[];
    valuation?: DeepAnalysisMetric[];
    financial_strength?: string[];
    growth?: string[];
    risks?: string[];
  };
  key_findings: {
    biggest_positive: string;
    biggest_negative: string;
    valuation_observation: string;
    health_observation: string;
  };
  agent_data?: AgentData;
}

function formatValue(value: any, rule: string, unit: string): string {
  if (value === null || value === undefined) return 'N/A';
  
  if (rule === 'percent') {
    return `${(Number(value) * 100).toFixed(2)}%`;
  }
  if (rule === 'large_currency' || rule === 'large_number') {
    const num = Number(value);
    const prefix = unit || '';
    if (num >= 1e12) return `${prefix}${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `${prefix}${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `${prefix}${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `${prefix}${(num / 1e3).toFixed(2)}K`;
    return `${prefix}${num.toLocaleString()}`;
  }
  if (rule === 'currency') {
    return `${unit}${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  }
  if (rule === 'multiple') {
    return `${Number(value).toFixed(2)}${unit}`;
  }
  
  if (typeof value === 'number') return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  return String(value);
}

export const DeepAnalyzePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [selectedSymbol, setSelectedSymbol] = useState(searchParams.get('symbol') || '');
  const [deepData, setDeepData] = useState<DeepData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawMetrics, setShowRawMetrics] = useState(false);

  const runAnalysis = async (sym: string) => {
    if (!sym) return;
    setIsLoading(true);
    setDeepData(null);
    setError(null);
    setShowRawMetrics(false);
    try {
      const result = await MarketService.deepAnalyze(sym);
      setDeepData(result);
    } catch {
      setError('Could not fetch data. This company may not have active data on Yahoo Finance.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const sym = searchParams.get('symbol');
    if (sym) {
      setSelectedSymbol(sym);
      runAnalysis(sym);
    }
  }, []);

  const handleAnalyze = () => runAnalysis(selectedSymbol);

  // Group metrics by category
  const metricsByCategory = deepData?.metrics.reduce((acc, metric) => {
    if (!acc[metric.category]) acc[metric.category] = [];
    acc[metric.category].push(metric);
    return acc;
  }, {} as Record<string, Metric[]>) || {};

  return (
    <div className="flex-1 p-6 w-full max-w-[1200px] mx-auto space-y-8 font-sans bg-[#060E0A] text-[#F5EFE6] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center space-x-3 pb-2">
        <div className="w-9 h-9 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
          <Activity className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-medium text-cream tracking-tight">Deep Analysis</h1>
          <p className="text-xs text-cream-muted">AI-driven analytical narrative</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 shadow-sm flex-shrink-0">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex-1">
            <SymbolSearch
              onSelect={setSelectedSymbol}
              placeholder="Search any listed company..."
              clearOnSelect={false}
            />
          </div>
          <button
            onClick={handleAnalyze}
            disabled={!selectedSymbol || isLoading}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-cream text-xs font-medium px-6 py-2.5 rounded-lg flex items-center justify-center space-x-2 shadow-sm transition-colors whitespace-nowrap h-full"
          >
            <Search className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Analyzing...' : 'Run Analysis'}</span>
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex flex-col items-center py-20 space-y-4">
          <Activity className="w-8 h-8 text-accent animate-pulse" />
          <div className="text-sm font-medium text-cream">Synthesizing Deep Analysis...</div>
          <div className="text-xs text-cream-muted">Reading historicals and writing the intelligence report.</div>
        </div>
      )}

      {error && (
        <div className="bg-[#1A0A0A] border border-semantic-red/30 rounded-xl p-4 text-xs text-semantic-red text-center flex-shrink-0">
          {error}
        </div>
      )}

      {deepData && (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {/* Header Title */}
          <div className="space-y-2 border-b border-hairline pb-6">
            <div className="flex items-center space-x-3">
              <h2 className="text-3xl font-semibold text-cream tracking-tight">{deepData.symbol.toUpperCase()}</h2>
              <span className="font-mono text-xs text-accent bg-accent/10 border border-accent/20 px-2 py-0.5 rounded">{deepData.ticker}</span>
            </div>
            <p className="text-lg text-semantic-green/90 font-medium">Overall Assessment: {deepData.overall_assessment}</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column (2/3): Core Analysis */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* Business Quality */}
              {deepData.deep_analysis?.business_quality && deepData.deep_analysis.business_quality.length > 0 && (
                <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4 shadow-sm">
                  <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                    <Briefcase className="w-4 h-4 text-accent" />
                    <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Business Quality</h3>
                  </div>
                  <div className="space-y-3">
                    {deepData.deep_analysis.business_quality.map((item, i) => (
                      <div key={i} className="flex flex-col sm:flex-row sm:items-baseline sm:space-x-2">
                        <span className="text-xs font-mono font-medium text-cream min-w-[120px]">{item.metric}: {item.value}</span>
                        <span className="text-[13px] text-cream-muted leading-relaxed">→ {item.interpretation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Valuation */}
              {deepData.deep_analysis?.valuation && deepData.deep_analysis.valuation.length > 0 && (
                <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4 shadow-sm">
                  <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                    <BarChart3 className="w-4 h-4 text-semantic-yellow" />
                    <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Valuation</h3>
                  </div>
                  <div className="space-y-3">
                    {deepData.deep_analysis.valuation.map((item, i) => (
                      <div key={i} className="flex flex-col sm:flex-row sm:items-baseline sm:space-x-2">
                        <span className="text-xs font-mono font-medium text-cream min-w-[120px]">{item.metric}: {item.value}</span>
                        <span className="text-[13px] text-cream-muted leading-relaxed">→ {item.interpretation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Growth & Financial Strength */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {deepData.deep_analysis.growth && deepData.deep_analysis.growth.length > 0 && (
                  <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4 shadow-sm">
                    <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                      <TrendingUp className="w-4 h-4 text-semantic-green" />
                      <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Growth</h3>
                    </div>
                    <ul className="space-y-3 list-disc list-inside text-[13px] text-cream-muted">
                      {deepData.deep_analysis.growth.map((item, i) => (
                        <li key={i} className="leading-relaxed">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {deepData.deep_analysis.financial_strength && deepData.deep_analysis.financial_strength.length > 0 && (
                  <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4 shadow-sm">
                    <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                      <Activity className="w-4 h-4 text-accent" />
                      <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Financial Strength</h3>
                    </div>
                    <ul className="space-y-3 list-disc list-inside text-[13px] text-cream-muted">
                      {deepData.deep_analysis.financial_strength.map((item, i) => (
                        <li key={i} className="leading-relaxed">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Risks */}
              {deepData.deep_analysis.risks && deepData.deep_analysis.risks.length > 0 && (
                <div className="bg-semantic-red/5 border border-semantic-red/10 rounded-xl p-6 space-y-4 shadow-sm">
                  <div className="flex items-center space-x-2 border-b border-semantic-red/10 pb-3">
                    <AlertTriangle className="w-4 h-4 text-semantic-red" />
                    <h3 className="text-sm font-medium text-semantic-red uppercase tracking-wider">Risks</h3>
                  </div>
                  <ul className="space-y-3 list-disc list-inside text-[13px] text-semantic-red/80">
                    {deepData.deep_analysis.risks.map((item, i) => (
                      <li key={i} className="leading-relaxed">{item}</li>
                    ))}
                  </ul>
                </div>
              )}

            </div>

            {/* Right Column (1/3): Key Findings */}
            <div className="space-y-6">
              <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-5 shadow-sm sticky top-6">
                <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                  <Lightbulb className="w-4 h-4 text-semantic-yellow" />
                  <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Key Findings</h3>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-1">
                    <div className="text-[10px] text-cream-muted uppercase tracking-wider font-semibold">Biggest Positive</div>
                    <div className="text-[13px] text-cream leading-relaxed">{deepData.key_findings.biggest_positive}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] text-cream-muted uppercase tracking-wider font-semibold">Biggest Negative</div>
                    <div className="text-[13px] text-cream leading-relaxed">{deepData.key_findings.biggest_negative}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] text-cream-muted uppercase tracking-wider font-semibold">Valuation Observation</div>
                    <div className="text-[13px] text-cream leading-relaxed">{deepData.key_findings.valuation_observation}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] text-cream-muted uppercase tracking-wider font-semibold">Financial Health</div>
                    <div className="text-[13px] text-cream leading-relaxed">{deepData.key_findings.health_observation}</div>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* Agent API Data Dashboard */}
          {deepData.agent_data && (
            <div className="pt-4 mt-8 animate-in fade-in duration-700">
              <div className="flex items-center space-x-2 border-b border-hairline pb-4 mb-6">
                <BarChart3 className="w-5 h-5 text-accent" />
                <h3 className="text-lg font-medium text-cream">Programmatic API Metrics (Deterministic API)</h3>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Valuation Metrics */}
                <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 shadow-sm">
                  <h4 className="text-sm font-medium text-cream-muted uppercase tracking-wider mb-4">Valuation</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Forward P/E</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{deepData.agent_data.valuation.forwardPE ? deepData.agent_data.valuation.forwardPE.toFixed(2) + 'x' : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Trailing P/E</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{deepData.agent_data.valuation.trailingPE ? deepData.agent_data.valuation.trailingPE.toFixed(2) + 'x' : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Price to Book</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{deepData.agent_data.valuation.priceToBook ? deepData.agent_data.valuation.priceToBook.toFixed(2) + 'x' : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Enterprise Value</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{formatValue(deepData.agent_data.valuation.enterpriseValue, 'large_currency', deepData.agent_data.current.currency === 'INR' ? '₹' : '$')}</span>
                    </div>
                  </div>
                </div>

                {/* Health Metrics */}
                <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 shadow-sm">
                  <h4 className="text-sm font-medium text-cream-muted uppercase tracking-wider mb-4">Health</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Net Debt</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{formatValue(deepData.agent_data.health.netDebt, 'large_currency', deepData.agent_data.current.currency === 'INR' ? '₹' : '$')}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Debt / Equity</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{deepData.agent_data.health.debtToEquity ? deepData.agent_data.health.debtToEquity.toFixed(2) + 'x' : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Current Ratio</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{deepData.agent_data.health.currentRatio ? deepData.agent_data.health.currentRatio.toFixed(2) : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-cream-muted">Cash Reserves</span>
                      <span className="text-[13px] text-cream font-mono font-medium">{formatValue(deepData.agent_data.health.cash, 'large_currency', deepData.agent_data.current.currency === 'INR' ? '₹' : '$')}</span>
                    </div>
                  </div>
                </div>

                {/* Growth Trends */}
                <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 shadow-sm">
                  <h4 className="text-sm font-medium text-cream-muted uppercase tracking-wider mb-4">Financials (Last 3 Years)</h4>
                  <div className="space-y-3">
                    {/* Header */}
                    <div className="flex justify-between items-center text-[10px] text-cream-muted uppercase tracking-wider border-b border-hairline pb-2">
                      <span className="w-8">Year</span>
                      <span className="text-right flex-1">Revenue</span>
                      <span className="text-right w-16">Op Margin</span>
                    </div>
                    {deepData.agent_data.financials.slice().reverse().slice(-3).reverse().map(yr => (
                      <div key={yr.year} className="flex justify-between items-center text-xs pt-1">
                        <span className="text-cream-muted w-8 font-medium">{yr.year}</span>
                        <span className="text-cream font-mono text-right flex-1">{formatValue(yr.revenue, 'large_currency', deepData.agent_data.current.currency === 'INR' ? '₹' : '$')}</span>
                        <span className="text-semantic-green font-mono text-right w-16">{yr.operatingMargin ? (yr.operatingMargin * 100).toFixed(1) + '%' : 'N/A'}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Supporting Evidence (Raw Metrics) */}
          <div className="pt-8">
            <button
              onClick={() => setShowRawMetrics(!showRawMetrics)}
              className="flex items-center space-x-2 text-sm text-cream-muted hover:text-cream transition-colors mx-auto"
            >
              <span>{showRawMetrics ? 'Hide Supporting Evidence' : 'View Supporting Evidence (Raw Metrics)'}</span>
              {showRawMetrics ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            
            {showRawMetrics && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
                {Object.entries(metricsByCategory).map(([category, metrics]) => (
                  <div key={category} className="bg-[#0D1912] border border-hairline rounded-xl overflow-hidden shadow-sm">
                    <div className="px-4 py-3 bg-[#14251B]/50 border-b border-hairline">
                      <span className="text-xs font-medium text-cream uppercase tracking-wider">{category}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-px bg-hairline">
                      {metrics.map((metric) => (
                        <div key={metric.key} className="bg-[#0D1912] p-3 space-y-1 relative group">
                          <div className="text-[9px] text-cream-muted uppercase tracking-wide leading-tight truncate" title={metric.label}>
                            {metric.label}
                          </div>
                          <div className="text-xs font-mono font-medium text-cream tabular-nums break-all">
                            {formatValue(metric.value, metric.format_rule, metric.unit)}
                          </div>
                          {metric.source === 'calculated' && (
                            <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <div className="text-[8px] bg-accent/20 text-accent px-1 rounded border border-accent/20">Calc</div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!deepData && !isLoading && !error && (
        <div className="flex flex-col items-center py-20 space-y-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent/5 border border-accent/10 flex items-center justify-center">
            <Microscope className="w-8 h-8 text-accent/40" />
          </div>
          <div>
            <div className="text-sm font-medium text-cream-muted">Search a company above</div>
            <div className="text-xs text-cream-dim mt-1">We'll reconstruct the full financial profile natively and generate an AI analytical narrative.</div>
          </div>
        </div>
      )}
    </div>
  );
};

