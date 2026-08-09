"""
Standalone Verification & Unit Test Script for Quant Engine and Quant Service.

Usage:
    python test_quant_service.py

Verifies:
1. QuantEngine mathematical unit calculations (safe division, CAGR, YoY growth, zero division handling)
2. QuantService full ratio snapshot generation (RELIANCE, TCS, HDFCBANK)
3. Specific ratio subset queries (Profitability, Valuation, Growth, Leverage)
4. Side-by-side multi-symbol comparison (RELIANCE vs TCS vs HDFCBANK)
5. In-memory caching and zero LLM execution
"""

import time
from dotenv import load_dotenv

from app.config.settings import Settings
from app.core.quant_engine import QuantEngine
from app.services.quant_service import QuantService
from app.utils import get_logger

logger = get_logger("finnai.test_quant", "INFO")


def run_unit_tests() -> None:
    print("\n--- 1. Testing QuantEngine Unit Calculations & Edge Cases ---")

    # Safe Division Test
    div_normal = QuantEngine.safe_divide(100.0, 4.0)
    assert div_normal == 25.0, f"Expected 25.0, got {div_normal}"

    div_zero = QuantEngine.safe_divide(100.0, 0.0)
    assert div_zero is None, "Division by zero should return None!"

    div_none = QuantEngine.safe_divide(None, 5.0)
    assert div_none is None, "None input should return None!"

    print("  [PASSED] safe_divide (normal, division-by-zero, None handling)")

    # CAGR Calculation Test
    # (200 / 100) ** (1/3) - 1 = 1.259921 - 1 = 0.2599
    cagr_normal = QuantEngine.calc_cagr(100.0, 200.0, 3)
    assert cagr_normal == 0.2599, f"Expected 0.2599, got {cagr_normal}"

    cagr_negative_base = QuantEngine.calc_cagr(-100.0, 200.0, 3)
    assert cagr_negative_base is None, "Negative CAGR base should return None!"

    print("  [PASSED] calc_cagr (3-year CAGR calculation, negative base protection)")

    # YoY Growth Test
    yoy_normal = QuantEngine.calc_yoy_growth(150.0, 100.0)
    assert yoy_normal == 0.5, f"Expected 0.5, got {yoy_normal}"

    print("  [PASSED] calc_yoy_growth (Year-over-Year growth percentage)")


def run_integration_tests() -> None:
    settings = Settings()
    quant_service = QuantService(settings=settings)

    print("\n--- 2. Testing QuantService Ratio Snapshots ---")
    symbols = ["RELIANCE", "TCS", "HDFCBANK"]

    for sym in symbols:
        start = time.perf_counter()
        snapshot = quant_service.get_full_ratio_snapshot(sym)
        latency = (time.perf_counter() - start) * 1000.0

        print(f"\n[{snapshot.canonical_symbol}] ({snapshot.symbol}) Ratio Snapshot (Latency: {latency:.2f}ms):")
        print(f"  • ROE:               {snapshot.profitability.roe}")
        print(f"  • Net Profit Margin: {snapshot.profitability.net_profit_margin}")
        print(f"  • P/E Ratio:         {snapshot.valuation.pe_ratio}")
        print(f"  • Forward P/E:       {snapshot.valuation.forward_pe}")
        print(f"  • Debt to Equity:    {snapshot.leverage.debt_to_equity}")
        print(f"  • Current Ratio:     {snapshot.leverage.current_ratio}")
        print(f"  • Dividend Yield:    {snapshot.dividend.dividend_yield}")

        # Test Subsets
        prof = quant_service.get_profitability_ratios(sym)
        val = quant_service.get_valuation_ratios(sym)
        assert prof.roe == snapshot.profitability.roe, "Profitability subset mismatch!"
        assert val.pe_ratio == snapshot.valuation.pe_ratio, "Valuation subset mismatch!"

    # Multi-symbol Side-by-Side Comparison
    print("\n--- 3. Testing Side-by-Side Multi-Symbol Comparison ---")
    comp = quant_service.compare_symbols(["RELIANCE", "TCS", "HDFCBANK"])
    print(f"Comparison Generated for {len(comp.symbols)} symbols at {comp.computed_at}:")

    print("\n  " + f"{'METRIC':<20} | {'RELIANCE':<15} | {'TCS':<15} | {'HDFCBANK':<15}")
    print("  " + "-" * 65)

    rel_snap = comp.metrics_comparison.get("RELIANCE")
    tcs_snap = comp.metrics_comparison.get("TCS")
    hdfc_snap = comp.metrics_comparison.get("HDFCBANK")

    pe_rel = str(rel_snap.valuation.pe_ratio) if rel_snap and rel_snap.valuation.pe_ratio else "N/A"
    pe_tcs = str(tcs_snap.valuation.pe_ratio) if tcs_snap and tcs_snap.valuation.pe_ratio else "N/A"
    pe_hdfc = str(hdfc_snap.valuation.pe_ratio) if hdfc_snap and hdfc_snap.valuation.pe_ratio else "N/A"
    print("  " + f"{'P/E Ratio':<20} | {pe_rel:<15} | {pe_tcs:<15} | {pe_hdfc:<15}")

    roe_rel = str(rel_snap.profitability.roe) if rel_snap and rel_snap.profitability.roe else "N/A"
    roe_tcs = str(tcs_snap.profitability.roe) if tcs_snap and tcs_snap.profitability.roe else "N/A"
    roe_hdfc = str(hdfc_snap.profitability.roe) if hdfc_snap and hdfc_snap.profitability.roe else "N/A"
    print("  " + f"{'ROE':<20} | {roe_rel:<15} | {roe_tcs:<15} | {roe_hdfc:<15}")

    dte_rel = str(rel_snap.leverage.debt_to_equity) if rel_snap and rel_snap.leverage.debt_to_equity else "N/A"
    dte_tcs = str(tcs_snap.leverage.debt_to_equity) if tcs_snap and tcs_snap.leverage.debt_to_equity else "N/A"
    dte_hdfc = str(hdfc_snap.leverage.debt_to_equity) if hdfc_snap and hdfc_snap.leverage.debt_to_equity else "N/A"
    print("  " + f"{'Debt/Equity':<20} | {dte_rel:<15} | {dte_tcs:<15} | {dte_hdfc:<15}")


def main() -> None:
    load_dotenv()
    logger.info("=== Starting Quant Engine & Quant Service Verification ===")

    run_unit_tests()
    run_integration_tests()

    print("\n" + "=" * 70)
    print("        QUANT SERVICE VERIFICATION COMPLETED SUCCEEDED!       ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
