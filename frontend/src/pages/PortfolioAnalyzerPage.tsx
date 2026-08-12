import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  ExternalLink,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
} from 'recharts';

// Need to match Tailwind's semantic colors from our new palette config conceptually
const COLORS = ['#5B7D4F', '#2D5F5F', '#B8860B', '#C75050', '#8A7B66', '#526A7E', '#A09789'];

export const PortfolioAnalyzerPage: React.FC = () => {
  const navigate = useNavigate();
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
          setAnalysis(data[0]);
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
      
      if (res.portfolio_metrics.total_pnl === 0 && res.portfolio_metrics.day_pnl === 0) {
        toast.error("[Beta] Yahoo query finance doesn't have active price data for these assets at the moment. Displaying invested values.", {
          duration: 6000,
          style: {
            background: 'var(--bg-secondary)',
            color: 'var(--tx-primary)',
            border: '1px solid var(--border)',
          }
        });
      }
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
        backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim() || '#F8F6F3',
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
    <div className="flex-1 p-8 w-full max-w-[1400px] mx-auto space-y-8 font-sans bg-bg-primary overflow-y-auto animate-page-in">
      {/* Page Title & Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <PieIcon className="w-6 h-6 text-accent" />
            <h1 className="text-2xl font-heading font-semibold text-tx-primary tracking-tight">Portfolio Analyzer</h1>
            <span className="text-xs font-mono bg-bg-tertiary text-tx-tertiary px-2 py-1 rounded-md border border-border">
              In Progress
            </span>
          </div>
          <p className="text-sm text-tx-secondary mt-2 max-w-2xl">
            Production-Grade Risk, NIFTY 50 Benchmark, Tax Loss Harvesting & Allocation Engine for NIFTY 500, ETFs & Mutual Funds
          </p>
        </div>

        {analysis && (
          <div className="flex items-center space-x-3 flex-wrap gap-y-2">
            <button
              onClick={handleExportPDF}
              disabled={isExportingPDF}
              className="flex items-center space-x-2 px-4 py-2 text-sm bg-accent text-white font-medium hover:bg-accent-hover rounded-lg nav-transition btn-press shadow-sm disabled:opacity-50"
            >
              {isExportingPDF ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <FileText className="w-4 h-4" />
              )}
              <span>{isExportingPDF ? 'Generating PDF...' : 'Export PDF Brief'}</span>
            </button>

            <button
              onClick={handleDownloadJSON}
              className="flex items-center space-x-2 px-4 py-2 text-sm bg-bg-secondary border border-border hover:border-accent text-tx-primary rounded-lg nav-transition btn-press"
            >
              <Download className="w-4 h-4 text-accent" />
              <span>JSON</span>
            </button>

            <button
              onClick={() => {
                setAnalysis(null);
                setFile(null);
              }}
              className="flex items-center space-x-2 px-4 py-2 text-sm bg-bg-secondary border border-border hover:border-border-strong text-tx-secondary hover:text-tx-primary rounded-lg nav-transition btn-press"
            >
              <RefreshCw className="w-4 h-4" />
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
            <div className="bg-bg-input border-2 border-dashed border-border hover:border-accent/60 rounded-2xl p-12 flex flex-col items-center justify-center text-center space-y-5 transition-all">
              <div className="w-16 h-16 rounded-full bg-accent-light flex items-center justify-center text-accent">
                <Upload className="w-8 h-8" />
              </div>

              <div>
                <h3 className="text-xl font-heading font-medium text-tx-primary">Upload Portfolio (.CSV, .XLSX)</h3>
                <p className="text-sm text-tx-secondary mt-2 max-w-lg">
                  Natively supports raw broker exports (Zerodha, Groww, etc.) with multiple sheets, or standard CSVs with <code className="font-mono text-accent">symbol</code>,{' '}
                  <code className="font-mono text-accent">quantity</code>, and{' '}
                  <code className="font-mono text-accent">avg_buy_price</code>.
                </p>
                <p className="text-xs text-accent mt-3 italic font-mono bg-accent-light px-3 py-1.5 rounded inline-block">
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

              <div className="flex items-center space-x-3 pt-4">
                <label
                  htmlFor="portfolio-csv-upload"
                  className="px-5 py-2.5 text-sm font-medium bg-bg-secondary border border-border text-tx-primary rounded-lg hover:border-border-strong nav-transition cursor-pointer shadow-sm"
                >
                  Select CSV or Excel File
                </label>

                {file && (
                  <span className="text-sm font-mono text-tx-secondary bg-bg-tertiary px-4 py-2.5 rounded-lg border border-border flex items-center space-x-2">
                    <FileSpreadsheet className="w-4 h-4 text-accent" />
                    <span>{file.name}</span>
                  </span>
                )}
              </div>

              {file && (
                <button
                  onClick={handleUploadAndAnalyze}
                  disabled={isAnalyzing}
                  className="w-full max-w-xs mt-6 py-3 px-4 text-sm font-medium bg-accent hover:bg-accent-hover text-white rounded-lg nav-transition flex items-center justify-center space-x-2 btn-press shadow-sm disabled:opacity-50"
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
              <div className="alert-danger text-sm text-semantic-red flex items-start space-x-3">
                <AlertTriangle className="w-5 h-5 text-semantic-red shrink-0 mt-0.5" />
                <p>{errorMsg}</p>
              </div>
            )}

            {/* Reference Sample Format */}
            <div className="surface-card p-6 space-y-4">
              <div className="flex items-center space-x-2 text-sm text-tx-primary font-medium font-heading">
                <Info className="w-4 h-4 text-accent" />
                <span>Standard CSV Format (Optional)</span>
              </div>
              <pre className="text-xs font-mono text-tx-secondary bg-bg-tertiary p-4 rounded-lg border border-border overflow-x-auto">
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
              <h3 className="text-sm font-medium text-tx-primary font-heading flex items-center space-x-2">
                <Clock className="w-4 h-4 text-accent" />
                <span>My Active Saved Portfolio</span>
              </h3>
              <span className="text-xs text-tx-tertiary font-mono">{savedAnalyses.length}/1</span>
            </div>

            {savedAnalyses.length === 0 ? (
              <div className="p-8 surface-card text-center text-sm text-tx-secondary leading-relaxed">
                No active saved portfolio found. Upload a portfolio CSV above to generate and automatically store your analysis.
              </div>
            ) : (
              <div className="space-y-4">
                {savedAnalyses.map((sa) => (
                  <div
                    key={sa.id}
                    onClick={() => setAnalysis(sa)}
                    className="surface-card p-6 cursor-pointer space-y-4 group card-interactive"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono text-accent font-semibold bg-accent-light px-2 py-1 rounded">Active Analysis</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (sa.id) handleDeleteSaved(sa.id);
                        }}
                        className="p-1.5 text-tx-tertiary hover:text-semantic-red opacity-0 group-hover:opacity-100 nav-transition rounded hover:bg-semantic-red-bg"
                        title="Delete Analysis"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="text-3xl font-mono text-tx-primary font-bold tracking-tight">
                      ₹{sa.portfolio_metrics.total_value.toLocaleString('en-IN')}
                    </div>

                    <div className="flex items-center justify-between text-sm text-tx-secondary">
                      <span>Risk Score: <strong className="text-tx-primary">{sa.portfolio_metrics.risk_score}/10</strong></span>
                      <span>Holdings: <strong className="text-tx-primary">{sa.holdings.length} Assets</strong></span>
                    </div>

                    <div className="text-xs text-tx-tertiary font-mono border-t border-border pt-4">
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
        <div id="portfolio-report-content" className="space-y-8 bg-bg-primary rounded-xl pt-2">
          {/* Executive Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="surface-card p-6 space-y-2">
              <span className="metric-label">Total Portfolio Value</span>
              <div className="text-2xl font-mono text-tx-primary font-semibold tracking-tight">
                ₹{analysis.portfolio_metrics.total_value.toLocaleString('en-IN')}
              </div>
              <span className="text-xs text-tx-tertiary font-mono block">
                Invested: ₹{analysis.portfolio_metrics.total_invested.toLocaleString('en-IN')}
              </span>
            </div>

            <div className="surface-card p-6 space-y-2">
              <span className="metric-label">Total P&L</span>
              <div
                className={`text-2xl font-mono font-semibold tracking-tight flex items-center space-x-1 ${
                  analysis.portfolio_metrics.total_pnl >= 0 ? 'text-semantic-green' : 'text-semantic-red'
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
              <span className="text-xs text-tx-tertiary font-mono block">
                Day Change: ₹{analysis.portfolio_metrics.day_pnl.toLocaleString('en-IN')}
              </span>
            </div>

            <div className="surface-card p-6 space-y-2">
              <span className="metric-label">Risk Score</span>
              <div className="flex items-center space-x-2">
                <span
                  className={`text-xl font-mono font-semibold px-3 py-1 rounded-md ${
                    analysis.portfolio_metrics.risk_score >= 7
                      ? 'bg-semantic-red-bg text-semantic-red border border-semantic-red/30'
                      : analysis.portfolio_metrics.risk_score >= 4
                      ? 'bg-semantic-amber-bg text-semantic-amber border border-semantic-amber/30'
                      : 'bg-semantic-green-bg text-semantic-green border border-semantic-green/30'
                  }`}
                >
                  {analysis.portfolio_metrics.risk_score} / 10
                </span>
              </div>
              <span className="text-xs text-tx-tertiary block mt-1">
                Max Exposure: {analysis.portfolio_metrics.concentration_risk_percent}%
              </span>
            </div>

            <div className="surface-card p-6 space-y-2">
              <span className="metric-label">Holdings Analyzed</span>
              <div className="text-2xl font-mono text-tx-primary font-semibold tracking-tight">
                {analysis.holdings.length} Assets
              </div>
              <span className="text-xs text-tx-tertiary font-mono block">
                Sectors: {Object.keys(analysis.allocation.sector_breakdown).length}
              </span>
            </div>
          </div>

          {/* Benchmark Comparison Card (NIFTY 50 Index) */}
          {analysis.benchmark_comparison && analysis.benchmark_comparison.length > 0 && (
            <div className="surface-card p-6 space-y-6 border-l-4 border-l-accent">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <h3 className="text-lg font-heading font-semibold text-tx-primary flex items-center space-x-2">
                  <Award className="w-5 h-5 text-accent" />
                  <span>Benchmark Comparison vs. NIFTY 50 Index (^NSEI)</span>
                </h3>
                <span className="text-xs text-tx-secondary bg-bg-tertiary px-3 py-1 rounded font-mono border border-border">Index Proxy: NIFTYBEES</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {analysis.benchmark_comparison.map((b) => (
                  <div key={b.period} className="bg-bg-input border border-border rounded-xl p-5 space-y-3">
                    <div className="flex items-center justify-between text-xs text-tx-secondary font-mono border-b border-border pb-2">
                      <span>{b.period} Horizon Return</span>
                      <span className="text-tx-primary font-bold">{b.period}</span>
                    </div>

                    <div className="flex items-center justify-between text-sm">
                      <span className="text-tx-secondary">Portfolio Return:</span>
                      <span className={`font-mono font-semibold ${b.portfolio_return_percent >= 0 ? 'text-semantic-green' : 'text-semantic-red'}`}>
                        {b.portfolio_return_percent}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-sm">
                      <span className="text-tx-secondary">NIFTY 50 Index:</span>
                      <span className="font-mono text-tx-primary font-medium">{b.nifty50_return_percent}%</span>
                    </div>

                    <div className="pt-3 mt-1 border-t border-border flex items-center justify-between text-sm">
                      <span className="text-tx-primary font-medium">Alpha (Outperformance):</span>
                      <span className={`font-mono font-bold px-2 py-1 rounded text-xs ${b.outperformance_percent >= 0 ? 'bg-semantic-green-bg text-semantic-green border border-semantic-green/30' : 'bg-semantic-red-bg text-semantic-red border border-semantic-red/30'}`}>
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
            <div className="alert-warm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-sm font-semibold text-semantic-amber font-heading">
                  <DollarSign className="w-5 h-5" />
                  <span>Automated Tax Loss Harvesting Opportunities</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider text-semantic-amber font-semibold bg-semantic-amber-bg border border-semantic-amber/20 px-2 py-1 rounded">Income Tax Act</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {analysis.tax_loss_harvesting.map((tlh) => (
                  <div key={tlh.symbol} className="bg-bg-secondary border border-border rounded-lg p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm font-semibold text-semantic-amber bg-semantic-amber-bg px-2 py-0.5 rounded border border-semantic-amber/20">${tlh.symbol}</span>
                      <span className="text-sm text-semantic-red font-mono font-semibold">
                        Loss: -₹{tlh.unrealized_loss.toLocaleString('en-IN')} ({tlh.unrealized_loss_percent}%)
                      </span>
                    </div>

                    <p className="text-sm text-tx-secondary leading-relaxed ai-answer-serif">{tlh.recommendation}</p>

                    <div className="flex items-center justify-between pt-3 border-t border-border text-xs font-mono text-tx-secondary">
                      <span>STCG Tax Saving: <strong className="text-semantic-green">₹{tlh.est_stcg_tax_saving.toLocaleString('en-IN')}</strong></span>
                      <span>LTCG Tax Saving: <strong className="text-semantic-green">₹{tlh.est_ltcg_tax_saving.toLocaleString('en-IN')}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Red Flags Banner */}
          {analysis.red_flags && analysis.red_flags.length > 0 && (
            <div className="alert-danger space-y-3">
              <div className="flex items-center space-x-2 text-sm font-semibold text-semantic-red font-heading">
                <ShieldAlert className="w-5 h-5" />
                <span>Critical Risk & Vulnerability Warnings</span>
              </div>
              <ul className="space-y-2 pl-1">
                {analysis.red_flags.map((flag, idx) => (
                  <li key={idx} className="text-sm text-tx-primary ai-answer-serif flex items-start space-x-3">
                    <span className="text-semantic-red mt-1">•</span>
                    <span className="leading-relaxed">{flag}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* AI Executive Overview */}
          <div className="surface-card p-6 space-y-4">
            <h3 className="text-sm font-semibold text-tx-primary flex items-center space-x-2 font-heading uppercase tracking-wider">
              <FileText className="w-4 h-4 text-accent" />
              <span>AI Analyst Portfolio Health Overview</span>
            </h3>
            <p className="ai-answer-serif text-[15px] text-tx-primary leading-relaxed whitespace-pre-line bg-bg-input p-5 rounded-lg border border-border">
              {analysis.summary}
            </p>
          </div>

          {/* Allocation Charts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="surface-card p-6 space-y-5">
              <h3 className="text-sm font-semibold text-tx-primary flex items-center space-x-2 font-heading uppercase tracking-wider border-b border-border pb-3">
                <PieIcon className="w-4 h-4 text-accent" />
                <span>Sector Allocation Breakdown</span>
              </h3>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sectorData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="43%"
                      outerRadius={70}
                    >
                      {sectorData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', color: 'var(--text-primary)', borderRadius: '8px', fontSize: '12px' }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      iconSize={10}
                      iconType="circle"
                      wrapperStyle={{ fontSize: '11px', fontFamily: 'var(--font-sans)', color: 'var(--text-secondary)' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="surface-card p-6 space-y-5">
              <h3 className="text-sm font-semibold text-tx-primary flex items-center space-x-2 font-heading uppercase tracking-wider border-b border-border pb-3">
                <BarChart3 className="w-4 h-4 text-accent" />
                <span>Asset Type Distribution</span>
              </h3>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={assetTypeData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <XAxis dataKey="name" stroke="var(--text-tertiary)" fontSize={12} tickMargin={10} />
                    <YAxis stroke="var(--text-tertiary)" fontSize={12} unit="%" />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', color: 'var(--text-primary)', borderRadius: '8px', fontSize: '12px' }}
                      cursor={{fill: 'var(--bg-hover)'}}
                    />
                    <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Strategic Rebalancing Suggestions */}
          {analysis.rebalancing_suggestions.length > 0 && (
            <div className="surface-card p-6 space-y-5">
              <h3 className="text-sm font-semibold text-tx-primary flex items-center space-x-2 font-heading uppercase tracking-wider border-b border-border pb-3">
                <RefreshCw className="w-4 h-4 text-accent" />
                <span>Strategic Rebalancing Suggestions</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {analysis.rebalancing_suggestions.map((sug, idx) => (
                  <div
                    key={idx}
                    className="bg-bg-input border border-border rounded-xl p-5 space-y-2"
                  >
                    <span className="font-mono text-sm text-accent font-semibold bg-accent-light px-2 py-0.5 rounded inline-block mb-1">Recommendation #{idx + 1}</span>
                    <p className="leading-relaxed text-sm text-tx-primary ai-answer-serif">{sug}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Detailed Holdings Table */}
          <div className="surface-card p-6 space-y-5 overflow-hidden">
            <h3 className="text-sm font-semibold text-tx-primary flex items-center space-x-2 font-heading uppercase tracking-wider border-b border-border pb-3">
              Asset Holdings Breakdown
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-tx-secondary whitespace-nowrap">
                <thead className="bg-bg-tertiary text-tx-primary border-y border-border font-mono uppercase text-xs">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Asset</th>
                    <th className="px-4 py-3 font-semibold">Type</th>
                    <th className="px-4 py-3 font-semibold">Sector</th>
                    <th className="px-4 py-3 font-semibold text-right">Qty</th>
                    <th className="px-4 py-3 font-semibold text-right">Avg Price</th>
                    <th className="px-4 py-3 font-semibold text-right">Current Price</th>
                    <th className="px-4 py-3 font-semibold text-right">Current Value</th>
                    <th className="px-4 py-3 font-semibold text-right">P&L (%)</th>
                    <th className="px-4 py-3 font-semibold text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border font-mono text-[13px]">
                  {sortedHoldings.map((h) => {
                    const hasValidPrice = h.current_price && h.current_price > 0 && h.current_price !== h.avg_buy_price;
                    const isGain = h.pnl >= 0;
                    return (
                      <tr key={h.symbol} className="hover:bg-bg-hover nav-transition">
                        <td className="px-4 py-3 font-semibold text-tx-primary">
                          <div className="flex items-center space-x-2">
                            <span>{h.symbol}</span>
                            {h.asset_type === 'stock' && (
                              <button
                                onClick={() => navigate(`/deep-analyze?symbol=${h.symbol}`)}
                                className="text-[10px] font-sans font-medium text-accent hover:text-accent-hover bg-accent-light px-1.5 py-0.5 rounded border border-accent/20 nav-transition flex items-center space-x-1"
                                title={`Run Deep Quantitative Analysis on ${h.symbol}`}
                              >
                                <ExternalLink className="w-2.5 h-2.5" />
                                <span>Deep Analyze</span>
                              </button>
                            )}
                          </div>
                          <span className="block text-[11px] font-sans text-tx-tertiary font-normal truncate max-w-[200px]">{h.name}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="uppercase text-[10px] text-accent font-semibold bg-accent-light px-2 py-0.5 rounded">{h.asset_type}</span>
                        </td>
                        <td className="px-4 py-3 font-sans text-tx-secondary">{h.sector}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{h.quantity}</td>
                        <td className="px-4 py-3 text-right tabular-nums">₹{h.avg_buy_price}</td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {hasValidPrice ? `₹${h.current_price}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums font-semibold text-tx-primary">
                          ₹{h.current_value.toLocaleString('en-IN')}
                        </td>
                        <td
                          className={`px-4 py-3 text-right tabular-nums font-semibold ${
                            !hasValidPrice
                              ? 'text-tx-tertiary'
                              : isGain
                              ? 'text-semantic-green'
                              : 'text-semantic-red'
                          }`}
                        >
                          {hasValidPrice ? (
                            <>
                              {isGain ? '+' : ''}
                              {h.pnl_percent}%
                            </>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-tx-primary">{h.weight_percent}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
