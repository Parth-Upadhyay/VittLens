import React, { useState, useEffect } from 'react';
import { PortfolioService } from '../services/api';
import { PortfolioSummary } from '../types';
import { MetricCard } from '../components/common/MetricCard';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { SymbolSearch } from '../components/common/SymbolSearch';
import { PieChart as PieChartIcon, Plus, Trash2 } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

const SYMBOLS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'BHARTIARTL', 'SBIN', 'ITC'];

const PIE_COLORS = ['#3D7A56', '#4ADE80', '#D97706', '#2E5E41', '#10B981', '#E55353', '#C4BCAD'];

export const PortfolioPage: React.FC = () => {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [symbol, setSymbol] = useState('RELIANCE');
  const [quantity, setQuantity] = useState('');
  const [avgPrice, setAvgPrice] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const loadPortfolio = async () => {
    setIsLoading(true);
    try {
      const data = await PortfolioService.getSummary();
      setSummary(data);
    } catch (e) {
      console.error('Failed to load portfolio:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPortfolio();
  }, []);

  const handleAddHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    const qty = parseFloat(quantity);
    const price = parseFloat(avgPrice);

    if (!qty || !price) return;

    try {
      await PortfolioService.addHolding(symbol, qty, price);
      setQuantity('');
      setAvgPrice('');
      setSymbol(''); // Force clear search if possible, or leave as is if we want them to add more
      await loadPortfolio();
    } catch (e) {
      console.error('Failed to add holding:', e);
    }
  };

  const handleRemoveHolding = async (id: number) => {
    try {
      await PortfolioService.removeHolding(id);
      await loadPortfolio();
    } catch (e) {
      console.error('Failed to remove holding:', e);
    }
  };

  if (isLoading || !summary) {
    return <LoadingSpinner message="Loading portfolio data..." className="bg-bg-primary h-full" />;
  }

  const pieData = summary.holdings.map((h) => ({
    name: h.symbol,
    value: h.market_value,
  }));

  return (
    <div className="flex-1 p-6 w-full max-w-[1600px] mx-auto space-y-6 font-sans bg-[#060E0A] text-[#F5EFE6]">
      <div className="flex items-center space-x-2.5 pb-2">
        <PieChartIcon className="w-5 h-5 text-accent" />
        <h1 className="text-xl font-medium text-cream tracking-tight">Portfolio Holdings & Asset Allocation</h1>
        <span className="bg-bg-tertiary text-tx-tertiary border border-border px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider font-semibold ml-3 flex items-center shadow-sm whitespace-nowrap">
          <span className="w-1.5 h-1.5 rounded-full bg-accent/70 animate-pulse mr-1.5"></span>
          In Progress
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Total Portfolio Value" value={`₹${summary.total_value.toLocaleString()}`} />
        <MetricCard label="Total Invested Cost" value={`₹${summary.total_cost.toLocaleString()}`} />
        <MetricCard
          label="Overall Unrealized P&L"
          value={`₹${summary.total_pnl.toLocaleString()}`}
          change={`${summary.total_pnl_percent >= 0 ? '+' : ''}${summary.total_pnl_percent}%`}
          isPositive={summary.total_pnl >= 0}
          isNegative={summary.total_pnl < 0}
        />
      </div>

      {/* Add Holding Form */}
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-3 shadow-sm">
        <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Add Position Holding</h2>
        <form onSubmit={handleAddHolding} className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <SymbolSearch 
            onSelect={setSymbol} 
            placeholder="Search company..."
            clearOnSelect={false}
          />

          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="Quantity (e.g. 10)"
            className="bg-[#14251B] border border-hairline text-xs text-cream placeholder-cream-dim rounded-lg px-3 py-2 focus:outline-none focus:border-accent font-sans"
          />

          <input
            type="number"
            value={avgPrice}
            onChange={(e) => setAvgPrice(e.target.value)}
            placeholder="Avg Buy Price ₹"
            className="bg-[#14251B] border border-hairline text-xs text-cream placeholder-cream-dim rounded-lg px-3 py-2 focus:outline-none focus:border-accent font-sans"
          />

          <button
            type="submit"
            className="bg-accent hover:bg-accent-hover text-cream text-xs font-medium px-4 py-2 rounded-lg flex items-center justify-center space-x-1 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add Position</span>
          </button>
        </form>
      </div>

      {/* Holdings Table & Allocation Pie */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Table (2 cols) */}
        <div className="lg:col-span-2 bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-3 overflow-x-auto shadow-sm">
          <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Holdings Positions</h2>
          {summary.holdings.length === 0 ? (
            <div className="py-8 text-center text-xs text-cream-muted">No positions added yet.</div>
          ) : (
            <table className="w-full text-xs text-left text-cream-muted font-sans">
              <thead className="text-cream border-b border-hairline font-normal text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2 text-right">Qty</th>
                  <th className="pb-2 text-right">Avg Price</th>
                  <th className="pb-2 text-right">Current Price</th>
                  <th className="pb-2 text-right">P&L</th>
                  <th className="pb-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {summary.holdings.map((h) => {
                  const isGain = h.pnl >= 0;
                  return (
                    <tr key={h.id} className="hover:bg-[#14251B]/50 transition-colors">
                      <td className="py-2.5 font-mono font-medium text-cream">{h.symbol}</td>
                      <td className="py-2.5 text-right font-mono tabular-nums">{h.quantity}</td>
                      <td className="py-2.5 text-right font-mono tabular-nums">₹{h.avg_price.toLocaleString()}</td>
                      <td className="py-2.5 text-right font-mono tabular-nums">₹{h.current_price.toLocaleString()}</td>
                      <td className={`py-2.5 text-right font-mono tabular-nums font-medium ${isGain ? 'text-semantic-green' : 'text-semantic-red'}`}>
                        {isGain ? '+' : ''}₹{h.pnl.toLocaleString()} ({h.pnl_percent}%)
                      </td>
                      <td className="py-2.5 text-right">
                        <button
                          onClick={() => handleRemoveHolding(h.id)}
                          className="p-1 text-cream-dim hover:text-semantic-red transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Allocation Pie Chart (1 col) */}
        <div className="bg-[#0D1912] border border-hairline rounded-xl p-4 space-y-3 flex flex-col justify-between shadow-sm">
          <h2 className="text-xs font-medium text-cream-muted uppercase tracking-wider">Asset Allocation</h2>
          {summary.holdings.length === 0 ? (
            <div className="py-12 text-center text-xs text-cream-muted">No data available</div>
          ) : (
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    innerRadius={45}
                    paddingAngle={3}
                  >
                    {pieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#0D1912', borderColor: 'rgba(245,239,230,0.12)', borderRadius: '8px', fontSize: '12px', color: '#F5EFE6' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
