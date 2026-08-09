import React, { useState, useEffect } from 'react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { PortfolioAnalyzerService } from '../services/api';
import { PortfolioAnalysisResponse, HoldingAnalysis } from '../types';
import {
  Upload,
  FileText,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  PieChart as PieIcon,
  BarChart3,
  Download,
  Trash2,
  Clock,
  CheckCircle2,
  RefreshCw,
  Info,
  DollarSign,
  FileSpreadsheet,
  Award,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
} from 'recharts';

const COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#10b981'];

export const PortfolioAnalyzerPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExportingPDF, setIsExportingPDF] = useState(false);
  const [analysis, setAnalysis] = useState<PortfolioAnalysisResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedAnalyses, setSavedAnalyses] = useState<PortfolioAnalysisResponse[]>([]);
  const [sortField, setSortField] = useState<keyof HoldingAnalysis>('current_value');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    loadSavedAnalyses();
  }, []);

  const loadSavedAnalyses = () => {
    PortfolioAnalyzerService.getSavedAnalyses()
      .then((data) => {
        setSavedAnalyses(data);
        if (data.length > 0 && !analysis) {
          setAnalysis(data[0]); // Display active saved portfolio
        }
      })
      .catch(() => setSavedAnalyses([]));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!file) return;
    setIsAnalyzing(true);
    setErrorMsg(null);

    try {
      const res = await PortfolioAnalyzerService.analyzePortfolio(file);
      setAnalysis(res);
      loadSavedAnalyses();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to analyze portfolio CSV.';
      setErrorMsg(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDeleteSaved = async (id: number) => {
    try {
      await PortfolioAnalyzerService.deleteAnalysis(id);
      loadSavedAnalyses();
      if (analysis && analysis.id === id) {
        setAnalysis(null);
      }
    } catch (err: any) {
      console.error('Delete failed:', err);
    }
  };

  const handleDownloadJSON = () => {
    if (!analysis) return;
    const jsonStr = JSON.stringify(analysis, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `portfolio_analysis_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPDF = async () => {
    const reportElem = document.getElementById('portfolio-report-content');
    if (!reportElem) return;
    setIsExportingPDF(true);

    try {
      const canvas = await html2canvas(reportElem, {
        scale: 2,
        backgroundColor: '#060E0A',
        useCORS: true,
      });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pdfWidth;
      const imgHeight = (canvas.height * pdfWidth) / canvas.width;

      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= pdfHeight;

      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pdfHeight;
      }

      pdf.save(`Executive_Portfolio_Report_${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch (err) {
      console.error('Failed to generate PDF:', err);
    } finally {
      setIsExportingPDF(false);
    }
  };

  const sortedHoldings = analysis
    ? [...analysis.holdings].sort((a, b) => {
        const valA = a[sortField] ?? 0;
        const valB = b[sortField] ?? 0;
        if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
        if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
        return 0;
      })
    : [];

  const sectorData = analysis
    ? Object.entries(analysis.allocation.sector_breakdown).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  const assetTypeData = analysis
    ? Object.entries(analysis.allocation.asset_type_breakdown).map(([name, value]) => ({
        name: name.toUpperCase(),
        value,
      }))
    : [];

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-8 font-sans bg-[#060E0A] text-[#F5EFE6]">
      {/* Page Title & Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-hairline pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <PieIcon className="w-6 h-6 text-accent" />
            <h1 className="text-2xl font-semibold text-cream tracking-tight">Portfolio Analyzer</h1>
          </div>
          <p className="text-xs text-cream-muted mt-1">
            Production-Grade Risk, NIFTY 50 Benchmark, Tax Loss Harvesting & Allocation Engine for NIFTY 500, ETFs & Mutual Funds
          </p>
        </div>

        {analysis && (
          <div className="flex items-center space-x-2.5 flex-wrap gap-y-2">
            <button
              onClick={handleExportPDF}
              disabled={isExportingPDF}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs bg-accent text-[#060E0A] font-semibold hover:bg-accent-hover rounded-lg transition-colors font-mono disabled:opacity-50"
            >
              {isExportingPDF ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileText className="w-3.5 h-3.5" />
              )}
              <span>{isExportingPDF ? 'Generating PDF...' : 'Export PDF Brief'}</span>
            </button>

            <button
              onClick={handleDownloadJSON}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs bg-[#0D1912] border border-hairline hover:border-accent text-cream rounded-lg transition-colors font-mono"
            >
              <Download className="w-3.5 h-3.5 text-accent" />
              <span>JSON</span>
            </button>

            <button
              onClick={() => {
                setAnalysis(null);
                setFile(null);
              }}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs bg-[#0D1912] border border-hairline hover:border-cream text-cream-muted rounded-lg transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Upload New File</span>
            </button>
          </div>
        )}
      </div>

      {/* Upload Zone or Active Analysis Dashboard */}
      {!analysis ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* CSV Upload Dropzone */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-[#0D1912] border-2 border-dashed border-hairline hover:border-accent/60 rounded-2xl p-10 flex flex-col items-center justify-center text-center space-y-4 transition-all">
              <div className="w-14 h-14 rounded-full bg-accent/10 flex items-center justify-center text-accent">
                <Upload className="w-7 h-7" />
              </div>

              <div>
                <h3 className="text-lg font-medium text-cream">Upload Portfolio (.CSV, .XLSX)</h3>
                <p className="text-xs text-cream-muted mt-1">
                  Natively supports raw broker exports (Zerodha, Groww, etc.) with multiple sheets, or standard CSVs with <code className="font-mono text-accent">symbol</code>,{' '}
                  <code className="font-mono text-accent">quantity</code>, and{' '}
                  <code className="font-mono text-accent">avg_buy_price</code>.
                </p>
                <p className="text-[11px] text-accent/80 mt-1.5 italic font-mono">
                  Note: Uploading a new portfolio instantly replaces your saved portfolio (1 portfolio per user limit).
                </p>
              </div>

              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                id="portfolio-csv-upload"
                onChange={handleFileChange}
                className="hidden"
              />

              <div className="flex items-center space-x-3 pt-2">
                <label
                  htmlFor="portfolio-csv-upload"
                  className="px-4 py-2 text-xs font-medium bg-accent text-[#060E0A] rounded-lg hover:bg-accent-hover transition-colors cursor-pointer"
                >
                  Select CSV or Excel File
                </label>

                {file && (
                  <span className="text-xs font-mono text-cream-muted bg-[#060E0A] px-3 py-1.5 rounded-md border border-hairline flex items-center space-x-1.5">
                    <FileSpreadsheet className="w-3.5 h-3.5 text-accent" />
                    <span>{file.name}</span>
                  </span>
                )}
              </div>

              {file && (
                <button
                  onClick={handleUploadAndAnalyze}
                  disabled={isAnalyzing}
                  className="w-full max-w-xs mt-4 py-2.5 px-4 text-xs font-medium bg-accent hover:bg-accent-hover text-[#060E0A] rounded-lg transition-colors flex items-center justify-center space-x-2 font-mono disabled:opacity-50"
                >
                  {isAnalyzing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Analyzing Portfolio...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Run Comprehensive Analysis</span>
                    </>
                  )}
                </button>
              )}
            </div>

            {errorMsg && (
              <div className="p-4 bg-red-950/40 border border-red-800/50 rounded-xl text-xs text-red-300 flex items-start space-x-3">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <p>{errorMsg}</p>
              </div>
            )}

            {/* Reference Sample Format */}
            <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-3">
              <div className="flex items-center space-x-2 text-xs text-cream font-medium">
                <Info className="w-4 h-4 text-accent" />
                <span>Standard CSV Format (Optional)</span>
              </div>
              <pre className="text-[11px] font-mono text-cream-muted bg-[#060E0A] p-3 rounded-lg border border-hairline overflow-x-auto">
{`symbol,name,quantity,avg_buy_price,date_acquired
RELIANCE,Reliance Industries Ltd,10,2450.00,2024-01-15
TCS,Tata Consultancy Services Ltd,5,3800.00,2024-02-10
HDFCBANK,HDFC Bank Ltd,20,1520.50,2024-03-01
NIFTYBEES,Nippon India ETF Nifty 50 BeES,100,260.00,2024-01-20
GOLDBEES,Nippon India ETF Gold BeES,200,105.00,2024-02-01`}
              </pre>
            </div>
          </div>

          {/* Saved Portfolio Card Sidebar */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-cream flex items-center space-x-2">
                <Clock className="w-4 h-4 text-accent" />
                <span>My Active Saved Portfolio</span>
              </h3>
              <span className="text-xs text-cream-muted font-mono">{savedAnalyses.length}/1</span>
            </div>

            {savedAnalyses.length === 0 ? (
              <div className="p-6 bg-[#0D1912] border border-hairline rounded-xl text-center text-xs text-cream-muted">
                No active saved portfolio found. Upload a portfolio CSV above to generate and automatically store your analysis.
              </div>
            ) : (
              <div className="space-y-3">
                {savedAnalyses.map((sa) => (
                  <div
                    key={sa.id}
                    onClick={() => setAnalysis(sa)}
                    className="bg-[#0D1912] border border-accent/40 rounded-xl p-5 cursor-pointer transition-all space-y-3 group hover:border-accent"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono text-accent font-semibold">Active Portfolio Analysis</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (sa.id) handleDeleteSaved(sa.id);
                        }}
                        className="p-1 text-cream-dim hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete Analysis"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="text-2xl font-mono text-cream font-bold">
                      ₹{sa.portfolio_metrics.total_value.toLocaleString('en-IN')}
                    </div>

                    <div className="flex items-center justify-between text-xs text-cream-muted">
                      <span>Risk Score: <strong className="text-cream">{sa.portfolio_metrics.risk_score}/10</strong></span>
                      <span>Holdings: <strong className="text-cream">{sa.holdings.length} Assets</strong></span>
                    </div>

                    <div className="text-[10px] text-cream-dim font-mono border-t border-hairline pt-2">
                      Saved At: {sa.created_at ? new Date(sa.created_at).toLocaleString() : 'Active Analysis'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Detailed Analysis Report Dashboard */
        <div id="portfolio-report-content" className="space-y-8 bg-[#060E0A] p-2 rounded-xl">
          {/* Executive Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-1">
              <span className="text-xs text-cream-muted">Total Portfolio Value</span>
              <div className="text-xl font-mono text-cream font-semibold">
                ₹{analysis.portfolio_metrics.total_value.toLocaleString('en-IN')}
              </div>
              <span className="text-[11px] text-cream-dim font-mono">
                Invested: ₹{analysis.portfolio_metrics.total_invested.toLocaleString('en-IN')}
              </span>
            </div>

            <div className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-1">
              <span className="text-xs text-cream-muted">Total P&L</span>
              <div
                className={`text-xl font-mono font-semibold flex items-center space-x-1 ${
                  analysis.portfolio_metrics.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {analysis.portfolio_metrics.total_pnl >= 0 ? (
                  <TrendingUp className="w-5 h-5 shrink-0" />
                ) : (
                  <TrendingDown className="w-5 h-5 shrink-0" />
                )}
                <span>
                  ₹{analysis.portfolio_metrics.total_pnl.toLocaleString('en-IN')} (
                  {analysis.portfolio_metrics.total_pnl_percent}%)
                </span>
              </div>
              <span className="text-[11px] text-cream-dim font-mono">
                Day Change: ₹{analysis.portfolio_metrics.day_pnl.toLocaleString('en-IN')}
              </span>
            </div>

            <div className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-1">
              <span className="text-xs text-cream-muted">Risk Score</span>
              <div className="flex items-center space-x-2">
                <span
                  className={`text-lg font-mono font-semibold px-2.5 py-0.5 rounded-md ${
                    analysis.portfolio_metrics.risk_score >= 7
                      ? 'bg-red-950 text-red-400 border border-red-800'
                      : analysis.portfolio_metrics.risk_score >= 4
                      ? 'bg-amber-950 text-amber-400 border border-amber-800'
                      : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  }`}
                >
                  {analysis.portfolio_metrics.risk_score} / 10
                </span>
              </div>
              <span className="text-[11px] text-cream-dim">
                Max Exposure: {analysis.portfolio_metrics.concentration_risk_percent}%
              </span>
            </div>

            <div className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-1">
              <span className="text-xs text-cream-muted">Holdings Analyzed</span>
              <div className="text-xl font-mono text-cream font-semibold">
                {analysis.holdings.length} Assets
              </div>
              <span className="text-[11px] text-cream-dim font-mono">
                Sectors: {Object.keys(analysis.allocation.sector_breakdown).length}
              </span>
            </div>
          </div>

          {/* Benchmark Comparison Card (NIFTY 50 Index) */}
          {analysis.benchmark_comparison && analysis.benchmark_comparison.length > 0 && (
            <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-cream flex items-center space-x-2">
                  <Award className="w-4.5 h-4.5 text-accent" />
                  <span>Benchmark Comparison vs. NIFTY 50 Index (^NSEI)</span>
                </h3>
                <span className="text-xs text-accent font-mono">Index Proxy: NIFTYBEES</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {analysis.benchmark_comparison.map((b) => (
                  <div key={b.period} className="bg-[#060E0A] border border-hairline rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs text-cream-muted font-mono">
                      <span>{b.period} Horizon Return</span>
                      <span className="text-cream font-bold">{b.period}</span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-cream-dim">Portfolio Return:</span>
                      <span className={`font-mono font-semibold ${b.portfolio_return_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {b.portfolio_return_percent}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-cream-dim">NIFTY 50 Index:</span>
                      <span className="font-mono text-cream">{b.nifty50_return_percent}%</span>
                    </div>

                    <div className="pt-2 border-t border-hairline flex items-center justify-between text-xs">
                      <span className="text-cream-muted font-medium">Alpha (Outperformance):</span>
                      <span className={`font-mono font-bold px-2 py-0.5 rounded text-[11px] ${b.outperformance_percent >= 0 ? 'bg-green-950 text-green-400 border border-green-800' : 'bg-red-950 text-red-400 border border-red-800'}`}>
                        {b.outperformance_percent >= 0 ? '+' : ''}{b.outperformance_percent}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Automated Tax Loss Harvesting Alerts Banner */}
          {analysis.tax_loss_harvesting && analysis.tax_loss_harvesting.length > 0 && (
            <div className="bg-amber-950/20 border border-amber-800/40 rounded-xl p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-sm font-semibold text-amber-400">
                  <DollarSign className="w-5 h-5" />
                  <span>Automated Tax Loss Harvesting Opportunities</span>
                </div>
                <span className="text-xs text-amber-300 font-mono">Income Tax Act Offset Rules</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {analysis.tax_loss_harvesting.map((tlh) => (
                  <div key={tlh.symbol} className="bg-[#060E0A] border border-amber-800/30 rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-amber-400">${tlh.symbol}</span>
                      <span className="text-xs text-red-400 font-mono font-semibold">
                        Unrealized Loss: -₹{tlh.unrealized_loss.toLocaleString('en-IN')} ({tlh.unrealized_loss_percent}%)
                      </span>
                    </div>

                    <p className="text-xs text-cream-muted leading-relaxed">{tlh.recommendation}</p>

                    <div className="flex items-center justify-between pt-2 border-t border-hairline text-[11px] font-mono text-cream-dim">
                      <span>Est. STCG Tax Saving: <strong className="text-green-400">₹{tlh.est_stcg_tax_saving.toLocaleString('en-IN')}</strong></span>
                      <span>Est. LTCG Tax Saving: <strong className="text-green-400">₹{tlh.est_ltcg_tax_saving.toLocaleString('en-IN')}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Red Flags Banner */}
          {analysis.red_flags && analysis.red_flags.length > 0 && (
            <div className="bg-red-950/30 border border-red-800/40 rounded-xl p-5 space-y-3">
              <div className="flex items-center space-x-2 text-xs font-semibold text-red-400">
                <ShieldAlert className="w-4 h-4" />
                <span>Critical Risk & Vulnerability Warnings</span>
              </div>
              <ul className="space-y-1.5">
                {analysis.red_flags.map((flag, idx) => (
                  <li key={idx} className="text-xs text-red-300/90 flex items-start space-x-2">
                    <span className="text-red-500">•</span>
                    <span>{flag}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* AI Executive Overview */}
          <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-3">
            <h3 className="text-sm font-medium text-cream flex items-center space-x-2">
              <FileText className="w-4 h-4 text-accent" />
              <span>AI Analyst Portfolio Health Overview</span>
            </h3>
            <p className="ai-answer-serif text-sm text-cream-muted leading-relaxed whitespace-pre-line">
              {analysis.summary}
            </p>
          </div>

          {/* Allocation Charts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4">
              <h3 className="text-xs font-medium text-cream flex items-center space-x-2">
                <PieIcon className="w-4 h-4 text-accent" />
                <span>Sector Allocation Breakdown</span>
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sectorData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {sectorData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#060E0A', borderColor: '#1F2923', color: '#F5EFE6' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-[#0D1912] border border-hairline rounded-xl p-5 space-y-4">
              <h3 className="text-xs font-medium text-cream flex items-center space-x-2">
                <BarChart3 className="w-4 h-4 text-accent" />
                <span>Asset Type Distribution</span>
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={assetTypeData}>
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} unit="%" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#060E0A', borderColor: '#1F2923', color: '#F5EFE6' }}
                    />
                    <Bar dataKey="value" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Strategic Rebalancing Suggestions */}
          {analysis.rebalancing_suggestions.length > 0 && (
            <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4">
              <h3 className="text-sm font-medium text-cream flex items-center space-x-2">
                <RefreshCw className="w-4 h-4 text-accent" />
                <span>Strategic Rebalancing Suggestions</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {analysis.rebalancing_suggestions.map((sug, idx) => (
                  <div
                    key={idx}
                    className="bg-[#060E0A] border border-hairline rounded-lg p-4 text-xs text-cream-muted space-y-1"
                  >
                    <span className="font-mono text-accent font-semibold">Recommendation #{idx + 1}</span>
                    <p className="leading-relaxed">{sug}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Detailed Holdings Table */}
          <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 space-y-4">
            <h3 className="text-sm font-medium text-cream">Asset Holdings Breakdown</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-cream-muted">
                <thead className="bg-[#060E0A] text-cream border-b border-hairline font-mono uppercase text-[11px]">
                  <tr>
                    <th className="p-3">Asset</th>
                    <th className="p-3">Type</th>
                    <th className="p-3">Sector</th>
                    <th className="p-3 text-right">Qty</th>
                    <th className="p-3 text-right">Avg Price</th>
                    <th className="p-3 text-right">Current Price</th>
                    <th className="p-3 text-right">Current Value</th>
                    <th className="p-3 text-right">P&L (%)</th>
                    <th className="p-3 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline font-mono">
                  {sortedHoldings.map((h) => (
                    <tr key={h.symbol} className="hover:bg-[#060E0A]/50 transition-colors">
                      <td className="p-3 font-semibold text-cream">
                        {h.symbol}
                        <span className="block text-[10px] font-sans text-cream-dim font-normal">{h.name}</span>
                      </td>
                      <td className="p-3 uppercase text-[10px] text-accent font-semibold">{h.asset_type}</td>
                      <td className="p-3 font-sans text-cream-muted">{h.sector}</td>
                      <td className="p-3 text-right tabular-nums">{h.quantity}</td>
                      <td className="p-3 text-right tabular-nums">₹{h.avg_buy_price}</td>
                      <td className="p-3 text-right tabular-nums">₹{h.current_price}</td>
                      <td className="p-3 text-right tabular-nums font-medium text-cream">
                        ₹{h.current_value.toLocaleString('en-IN')}
                      </td>
                      <td
                        className={`p-3 text-right tabular-nums font-semibold ${
                          h.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {h.pnl >= 0 ? '+' : ''}
                        {h.pnl_percent}%
                      </td>
                      <td className="p-3 text-right tabular-nums text-accent">{h.weight_percent}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
