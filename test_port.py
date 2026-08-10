from app.agents.portfolio_agent import PortfolioAgent
from app.schemas import PortfolioState, Holding

def test():
    pa = PortfolioAgent()
    state = PortfolioState(
        holdings=[Holding(symbol="NIFTYBEES", quantity=100, avg_buy_price=200.0)],
        metrics=None,
        sector_allocation={},
        benchmark_comparison=[],
        tax_loss_harvesting=[],
        raw_market_data={},
        raw_quant_data={}
    )
    # Compute metrics first to get total PNL
    state = pa.node_compute_metrics(state)
    # Then fetch benchmarks
    state = pa.node_fetch_benchmarks(state)
    
    print("Metrics PNL %:", state["metrics"].total_pnl_percent)
    print("Benchmarks:")
    for b in state["benchmark_comparison"]:
        print(f"{b.period}: NIFTY={b.nifty50_return_percent}% | Port={b.portfolio_return_percent}% | Alpha={b.outperformance_percent}%")

if __name__ == "__main__":
    test()
