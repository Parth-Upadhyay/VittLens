import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Microscope, Search, ChevronDown, ChevronUp, AlertTriangle, Lightbulb, Activity } from 'lucide-react';
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

interface DeepData {
  symbol: string;
  ticker: string;
  metrics: Metric[];
  snapshots: Record<string, string>;
  key_insights: { title: string; description: string; type: string }[];
  red_flags: { title: string; description: string; type: string }[];
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

const getRatingColor = (rating: string) => {
  const r = rating?.toLowerCase() || '';
  if (r === 'strong' || r === 'excellent') return 'text-semantic-green bg-semantic-green/10 border-semantic-green/20';
  if (r === 'moderate' || r === 'good' || r === 'reasonable') return 'text-semantic-yellow bg-semantic-yellow/10 border-semantic-yellow/20';
  if (r === 'weak' || r === 'poor' || r === 'overvalued') return 'text-semantic-red bg-semantic-red/10 border-semantic-red/20';
  if (r === 'undervalued') return 'text-semantic-green bg-semantic-green/10 border-semantic-green/20';
  return 'text-cream-muted bg-white/5 border-white/10';
};

const getRatingEmoji = (rating: string) => {
  const r = rating?.toLowerCase() || '';
  if (r === 'strong' || r === 'excellent' || r === 'undervalued') return '🟢';
  if (r === 'moderate' || r === 'good' || r === 'reasonable') return '🟡';
  if (r === 'weak' || r === 'poor' || r === 'overvalued') return '🔴';
  return '⚪';
};

export const DeepAnalyzePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [selectedSymbol, setSelectedSymbol] = useState(searchParams.get('symbol') || '');
  const [deepData, setDeepData] = useState<DeepData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  const runAnalysis = async (sym: string) => {
    if (!sym) return;
    setIsLoading(true);
    setDeepData(null);
    setError(null);
    try {
      const result = await MarketService.deepAnalyze(sym);
      setDeepData(result);
      
      const expanded: Record<string, boolean> = {};
      const categories = [...new Set(result.metrics.map((m: Metric) => m.category))];
      categories.forEach(c => { expanded[c as string] = true; });
      setExpandedGroups(expanded);
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

  const toggleGroup = (label: string) => {
    setExpandedGroups(prev => ({ ...prev, [label]: !prev[label] }));
  };

  // Group metrics by category
  const metricsByCategory = deepData?.metrics.reduce((acc, metric) => {
    if (!acc[metric.category]) acc[metric.category] = [];
    acc[metric.category].push(metric);
    return acc;
  }, {} as Record<string, Metric[]>) || {};

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center space-x-3 pb-2">
        <div className="w-9 h-9 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
          <Activity className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-medium text-cream tracking-tight">Financial Intelligence Engine</h1>
          <p className="text-xs text-cream-muted">Normalized historical metrics and AI-driven insights</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm flex-shrink-0">
        <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Select Company</h2>
        <div className="flex items-center gap-3">
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
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-cream text-xs font-medium px-5 py-2 rounded-lg flex items-center space-x-2 shadow-sm transition-colors whitespace-nowrap"
          >
            <Search className="w-3.5 h-3.5" />
            <span>{isLoading ? 'Analyzing...' : 'Run Analysis'}</span>
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex flex-col items-center py-16 space-y-4">
          <Activity className="w-8 h-8 text-accent animate-pulse" />
          <div className="text-sm font-medium text-cream">Running Financial Intelligence Engine...</div>
          <div className="text-xs text-cream-muted">Extracting multi-year financials, computing normalizations, and generating AI insights.</div>
        </div>
      )}

      {error && (
        <div className="bg-[#1A0A0A] border border-semantic-red/30 rounded-xl p-4 text-xs text-semantic-red text-center flex-shrink-0">
          {error}
        </div>
      )}

      {deepData && (
        <div className="space-y-6">
          {/* Summary Bar */}
          <div className="flex items-center justify-between flex-shrink-0">
            <div>
              <span className="text-lg font-medium text-cream">{deepData.symbol.toUpperCase()}</span>
              <span className="ml-3 font-mono text-xs text-accent bg-[#0D1912] border border-hairline px-2 py-0.5 rounded">{deepData.ticker}</span>
            </div>
            <span className="text-xs text-cream-muted tabular-nums">{deepData.metrics.length} metrics calculated</span>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            
            {/* Left Column: Metrics Tables */}
            <div className="xl:col-span-2 space-y-4">
              {Object.entries(metricsByCategory).map(([category, metrics]) => {
                const isOpen = expandedGroups[category] !== false;
                return (
                  <div key={category} className="bg-[#0D1912] border border-hairline rounded-xl overflow-hidden shadow-sm flex-shrink-0">
                    <button
                      onClick={() => toggleGroup(category)}
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#14251B]/50 transition-colors"
                    >
                      <div className="flex items-center space-x-2.5">
                        <span className="text-xs font-medium text-cream uppercase tracking-wider">{category}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] text-cream-muted tabular-nums">{metrics.length} metrics</span>
                        {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-cream-muted" /> : <ChevronDown className="w-3.5 h-3.5 text-cream-muted" />}
                      </div>
                    </button>

                    {isOpen && (
                      <div className="border-t border-hairline bg-hairline">
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-px">
                          {metrics.map((metric) => (
                            <div key={metric.key} className="bg-[#0D1912] p-4 space-y-1.5 hover:bg-[#14251B]/30 transition-colors relative group">
                              <div className="text-[10px] text-cream-muted uppercase tracking-wide leading-tight">{metric.label}</div>
                              <div className="flex items-end justify-between">
                                <div className="text-sm font-mono font-medium text-cream tabular-nums break-all">
                                  {formatValue(metric.value, metric.format_rule, metric.unit)}
                                </div>
                              </div>
                              {metric.source === 'calculated' && (
                                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <div className="text-[8px] bg-accent/20 text-accent px-1.5 py-0.5 rounded border border-accent/20">Calculated</div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Right Column: AI Insights */}
            <div className="space-y-4">
              
              {/* Financial Snapshot */}
              <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm flex-shrink-0">
                <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                  <Activity className="w-4 h-4 text-accent" />
                  <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Financial Snapshot</h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(deepData.snapshots || {}).map(([key, rating]) => (
                    <div key={key} className="space-y-1">
                      <div className="text-[10px] text-cream-muted uppercase tracking-wide">{key.replace('_', ' ')}</div>
                      <div className={`text-[11px] font-medium px-2 py-1 rounded border inline-flex items-center space-x-1.5 ${getRatingColor(rating)}`}>
                        <span>{getRatingEmoji(rating)}</span>
                        <span>{rating}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Key Insights */}
              <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm flex-shrink-0">
                <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                  <Lightbulb className="w-4 h-4 text-semantic-green" />
                  <h3 className="text-sm font-medium text-cream uppercase tracking-wider">Key Insights</h3>
                </div>
                <div className="space-y-4">
                  {deepData.key_insights?.map((insight, idx) => (
                    <div key={idx} className="space-y-1">
                      <div className="flex items-start space-x-2">
                        <span className="text-xs font-medium text-cream">{idx + 1}. {insight.title}</span>
                      </div>
                      <p className="text-[11px] text-cream-muted leading-relaxed pl-4 border-l border-hairline ml-1">
                        {insight.description}
                      </p>
                    </div>
                  ))}
                  {!deepData.key_insights?.length && (
                    <div className="text-xs text-cream-muted italic">No insights generated.</div>
                  )}
                </div>
              </div>

              {/* Things to Watch */}
              <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4 shadow-sm flex-shrink-0">
                <div className="flex items-center space-x-2 border-b border-hairline pb-3">
                  <AlertTriangle className="w-4 h-4 text-semantic-red" />
                  <h3 className="text-sm font-medium text-semantic-red uppercase tracking-wider">Things to Watch</h3>
                </div>
                <div className="space-y-3">
                  {deepData.red_flags?.map((flag, idx) => (
                    <div key={idx} className="bg-semantic-red/5 border border-semantic-red/10 rounded-lg p-3 space-y-1">
                      <div className="text-xs font-medium text-semantic-red">{flag.title}</div>
                      <p className="text-[11px] text-semantic-red/70 leading-relaxed">
                        {flag.description}
                      </p>
                    </div>
                  ))}
                  {!deepData.red_flags?.length && (
                    <div className="text-xs text-cream-muted italic">No red flags identified.</div>
                  )}
                </div>
              </div>

            </div>
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
            <div className="text-xs text-cream-dim mt-1">We'll reconstruct the full financial profile natively and generate AI-driven insights.</div>
          </div>
        </div>
      )}
    </div>
  );
};
