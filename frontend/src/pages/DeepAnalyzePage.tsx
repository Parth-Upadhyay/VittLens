import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Microscope, Search, ChevronDown, ChevronUp, AlertTriangle, Lightbulb, Activity, TrendingUp, Shield, BarChart3, Briefcase } from 'lucide-react';
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
    <div className="flex-1 p-8 w-full max-w-[1400px] mx-auto space-y-8 font-sans bg-bg-primary overflow-y-auto animate-page-in">
      {/* Header */}
      <div className="flex items-center space-x-3 pb-2">
        <div className="w-10 h-10 rounded-lg bg-accent-light border border-accent/20 flex items-center justify-center">
          <Activity className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-semibold text-tx-primary tracking-tight">Deep Analysis</h1>
          <p className="text-xs text-tx-secondary">AI-driven analytical narrative</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="surface-card p-5 flex flex-col sm:flex-row sm:items-center gap-4">
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
          className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium px-6 py-2.5 rounded-lg flex items-center justify-center space-x-2 shadow-sm nav-transition btn-press whitespace-nowrap h-[42px]"
        >
          <Search className="w-4 h-4" />
          <span>{isLoading ? 'Analyzing...' : 'Run Analysis'}</span>
        </button>
      </div>

      {isLoading && (
        <div className="flex flex-col items-center py-20 space-y-4">
          <Activity className="w-8 h-8 text-accent animate-pulse" />
          <div className="text-sm font-medium text-tx-primary">Synthesizing Deep Analysis...</div>
          <div className="text-xs text-tx-secondary">Reading historicals and writing the intelligence report.</div>
        </div>
      )}

      {error && (
        <div className="alert-danger text-xs text-semantic-red">
          {error}
        </div>
      )}

      {deepData && (
        <div className="space-y-8 animate-page-in">
          {/* Header Title */}
          <div className="space-y-2 border-b border-border pb-6">
            <div className="flex items-center space-x-3">
              <h2 className="text-3xl font-heading font-semibold text-tx-primary tracking-tight">{deepData.symbol.toUpperCase()}</h2>
              <span className="font-mono text-xs text-accent bg-accent-light border border-accent/20 px-2 py-0.5 rounded">{deepData.ticker}</span>
            </div>
            <p className="text-lg text-semantic-green font-medium">Overall Assessment: {deepData.overall_assessment}</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column (2/3): Core Analysis */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* Business Quality */}
              {deepData.deep_analysis?.business_quality && deepData.deep_analysis.business_quality.length > 0 && (
                <div className="surface-card p-6 space-y-4">
                  <div className="flex items-center space-x-2 border-b border-border pb-3">
                    <Briefcase className="w-4 h-4 text-accent" />
                    <h3 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Business Quality</h3>
                  </div>
                  <div className="space-y-3">
                    {deepData.deep_analysis.business_quality.map((item, i) => (
                      <div key={i} className="flex flex-col sm:flex-row sm:items-baseline sm:space-x-2">
                        <span className="text-sm font-mono font-medium text-tx-primary min-w-[140px]">{item.metric}: {item.value}</span>
                        <span className="text-sm text-tx-secondary ai-answer-serif leading-relaxed">→ {item.interpretation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Valuation */}
              {deepData.deep_analysis?.valuation && deepData.deep_analysis.valuation.length > 0 && (
                <div className="surface-card p-6 space-y-4">
                  <div className="flex items-center space-x-2 border-b border-border pb-3">
                    <BarChart3 className="w-4 h-4 text-semantic-amber" />
                    <h3 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Valuation</h3>
                  </div>
                  <div className="space-y-3">
                    {deepData.deep_analysis.valuation.map((item, i) => (
                      <div key={i} className="flex flex-col sm:flex-row sm:items-baseline sm:space-x-2">
                        <span className="text-sm font-mono font-medium text-tx-primary min-w-[140px]">{item.metric}: {item.value}</span>
                        <span className="text-sm text-tx-secondary ai-answer-serif leading-relaxed">→ {item.interpretation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Growth & Financial Strength */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {deepData.deep_analysis.growth && deepData.deep_analysis.growth.length > 0 && (
                  <div className="surface-card p-6 space-y-4">
                    <div className="flex items-center space-x-2 border-b border-border pb-3">
                      <TrendingUp className="w-4 h-4 text-semantic-green" />
                      <h3 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Growth</h3>
                    </div>
                    <ul className="space-y-3 list-disc list-inside text-sm text-tx-secondary ai-answer-serif">
                      {deepData.deep_analysis.growth.map((item, i) => (
                        <li key={i} className="leading-relaxed">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {deepData.deep_analysis.financial_strength && deepData.deep_analysis.financial_strength.length > 0 && (
                  <div className="surface-card p-6 space-y-4">
                    <div className="flex items-center space-x-2 border-b border-border pb-3">
                      <Activity className="w-4 h-4 text-accent" />
                      <h3 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Financial Strength</h3>
                    </div>
                    <ul className="space-y-3 list-disc list-inside text-sm text-tx-secondary ai-answer-serif">
                      {deepData.deep_analysis.financial_strength.map((item, i) => (
                        <li key={i} className="leading-relaxed">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Risks */}
              {deepData.deep_analysis.risks && deepData.deep_analysis.risks.length > 0 && (
                <div className="alert-warm">
                  <div className="flex items-center space-x-2 border-b border-semantic-amber/20 pb-3 mb-3">
                    <AlertTriangle className="w-4 h-4 text-semantic-amber" />
                    <h3 className="text-sm font-semibold text-semantic-amber uppercase tracking-wider font-heading">Risks</h3>
                  </div>
                  <ul className="space-y-3 list-disc list-inside text-sm text-tx-primary ai-answer-serif">
                    {deepData.deep_analysis.risks.map((item, i) => (
                      <li key={i} className="leading-relaxed">{item}</li>
                    ))}
                  </ul>
                </div>
              )}

            </div>

            {/* Right Column (1/3): Key Findings */}
            <div className="space-y-6">
              <div className="surface-card p-6 space-y-5 sticky top-6">
                <div className="flex items-center space-x-2 border-b border-border pb-3">
                  <Lightbulb className="w-4 h-4 text-semantic-amber" />
                  <h3 className="text-sm font-semibold text-tx-primary uppercase tracking-wider font-heading">Key Findings</h3>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-1">
                    <div className="text-[11px] text-tx-secondary uppercase tracking-wider font-semibold">Biggest Positive</div>
                    <div className="text-[14px] text-tx-primary ai-answer-serif leading-relaxed">{deepData.key_findings.biggest_positive}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[11px] text-tx-secondary uppercase tracking-wider font-semibold">Biggest Negative</div>
                    <div className="text-[14px] text-tx-primary ai-answer-serif leading-relaxed">{deepData.key_findings.biggest_negative}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[11px] text-tx-secondary uppercase tracking-wider font-semibold">Valuation Observation</div>
                    <div className="text-[14px] text-tx-primary ai-answer-serif leading-relaxed">{deepData.key_findings.valuation_observation}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[11px] text-tx-secondary uppercase tracking-wider font-semibold">Financial Health</div>
                    <div className="text-[14px] text-tx-primary ai-answer-serif leading-relaxed">{deepData.key_findings.health_observation}</div>
                  </div>
                </div>
              </div>
            </div>

          </div>



          {/* Supporting Evidence (Raw Metrics) */}
          <div className="pt-10">
            <button
              onClick={() => setShowRawMetrics(!showRawMetrics)}
              className="flex items-center space-x-2 text-sm font-medium text-tx-secondary hover:text-tx-primary nav-transition mx-auto"
            >
              <span>{showRawMetrics ? 'Hide Supporting Evidence' : 'View Supporting Evidence (Raw Metrics)'}</span>
              {showRawMetrics ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            
            {showRawMetrics && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-page-in">
                {Object.entries(metricsByCategory).map(([category, metrics]) => (
                  <div key={category} className="surface-card overflow-hidden">
                    <div className="px-5 py-4 bg-bg-tertiary border-b border-border">
                      <span className="text-xs font-semibold text-tx-primary uppercase tracking-wider font-heading">{category}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-px bg-border">
                      {metrics.map((metric) => (
                        <div key={metric.key} className="bg-bg-secondary p-4 space-y-1 relative group">
                          <div className="text-[10px] text-tx-secondary uppercase tracking-wide leading-tight truncate" title={metric.label}>
                            {metric.label}
                          </div>
                          <div className="text-sm font-mono font-medium text-tx-primary tabular-nums break-all">
                            {formatValue(metric.value, metric.format_rule, metric.unit)}
                          </div>
                          {metric.source === 'calculated' && (
                            <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                              <div className="text-[9px] bg-accent-light text-accent px-1.5 py-0.5 rounded border border-accent/20">Calc</div>
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
        <div className="flex flex-col items-center py-24 space-y-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-accent-light border border-accent/20 flex items-center justify-center">
            <Microscope className="w-8 h-8 text-accent" />
          </div>
          <div>
            <div className="text-lg font-heading font-semibold text-tx-primary">Search a company above</div>
            <div className="text-sm text-tx-secondary mt-1 max-w-md mx-auto">We'll reconstruct the full financial profile natively and generate an AI analytical narrative.</div>
          </div>
        </div>
      )}
    </div>
  );
};
