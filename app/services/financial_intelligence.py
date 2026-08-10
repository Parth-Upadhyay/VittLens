import json
import math
from typing import Dict, Any, List, Optional
from app.services.factory import get_llm_provider
from app.utils import get_logger

logger = get_logger("finnai.financial_intelligence")

class FinancialIntelligenceService:
    """
    Normalizes raw financial data, computes historical metrics, and generates LLM-powered financial intelligence.
    """

    def __init__(self):
        self.llm = get_llm_provider()

    def _get_val(self, df, key, year_idx=0):
        if df is None or key not in df.index or df.empty:
            return None
        try:
            # df.iloc[:, year_idx] gets the column for a specific year (0 = most recent)
            if year_idx >= len(df.columns):
                return None
            val = df.loc[key].iloc[year_idx]
            if val is None:
                return None
            fval = float(val)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        except Exception:
            return None

    def _compute_cagr(self, current_val, past_val, years):
        if not current_val or not past_val or past_val <= 0 or current_val <= 0 or years <= 0:
            return None
        return ((current_val / past_val) ** (1 / years)) - 1

    def normalize_metrics(self, ticker_symbol: str, fast_info: Any, financials: Any, balance_sheet: Any, info: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        metrics = []
        info = info or {}

        # Currency mismatch check
        currency = info.get("currency") or getattr(fast_info, "currency", None)
        financial_currency = info.get("financialCurrency")
        is_currency_mismatch = currency and financial_currency and currency != financial_currency

        # Current values
        net_income = self._get_val(financials, "Net Income")
        total_revenue = self._get_val(financials, "Total Revenue")
        operating_income = self._get_val(financials, "Operating Income")
        ebitda = self._get_val(financials, "EBITDA") or self._get_val(financials, "Normalized EBITDA")
        ebit = self._get_val(financials, "EBIT") or operating_income

        equity = self._get_val(balance_sheet, "Stockholders Equity") or self._get_val(balance_sheet, "Total Equity Gross Minority Interest")
        total_assets = self._get_val(balance_sheet, "Total Assets")
        current_liabilities = self._get_val(balance_sheet, "Current Liabilities")
        total_debt = self._get_val(balance_sheet, "Total Debt")
        total_cash = self._get_val(balance_sheet, "Cash And Cash Equivalents") or self._get_val(balance_sheet, "Cash Cash Equivalents And Short Term Investments")

        price = getattr(fast_info, "last_price", None)
        market_cap = getattr(fast_info, "market_cap", None)
        shares = getattr(fast_info, "shares", None)
        year_high = getattr(fast_info, "year_high", None)
        year_low = getattr(fast_info, "year_low", None)
        volume = getattr(fast_info, "last_volume", None)

        def add_metric(category, key, label, value, unit="", format_rule="standard"):
            if value is not None:
                metrics.append({
                    "category": category,
                    "key": key,
                    "label": label,
                    "value": round(value, 4) if isinstance(value, float) else value,
                    "unit": unit,
                    "format_rule": format_rule,
                    "source": "calculated"
                })

        # Market Snapshot
        add_metric("Market Snapshot", "currentPrice", "Current Price", price, "₹", "currency")
        add_metric("Market Snapshot", "marketCap", "Market Cap", market_cap, "₹", "large_currency")
        add_metric("Market Snapshot", "yearHigh", "52W High", year_high, "₹", "currency")
        add_metric("Market Snapshot", "yearLow", "52W Low", year_low, "₹", "currency")
        add_metric("Market Snapshot", "volume", "Volume", volume, "", "large_number")
        
        if price and year_high and year_low and year_high > year_low:
            position = (price - year_low) / (year_high - year_low)
            add_metric("Market Snapshot", "52WPosition", "52W Position", position, "%", "percent")

        # Valuation
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        peg = info.get("pegRatio")
        dividend_yield = info.get("dividendYield")
        eps = info.get("trailingEps")

        if eps is None and net_income and shares and shares != 0:
            if not is_currency_mismatch:
                eps = net_income / shares
        
        if pe is not None:
            add_metric("Valuation", "peRatio", "P/E Ratio", pe, "x", "multiple")
        elif not is_currency_mismatch and price and eps and eps > 0:
            pe = price / eps
            add_metric("Valuation", "peRatio", "P/E Ratio", pe, "x", "multiple")
        
        if pb is not None:
            add_metric("Valuation", "priceToBook", "Price to Book", pb, "x", "multiple")
        elif not is_currency_mismatch and market_cap and equity and equity > 0:
            add_metric("Valuation", "priceToBook", "Price to Book", market_cap / equity, "x", "multiple")

        if peg is not None:
            add_metric("Valuation", "pegRatio", "PEG Ratio", peg, "x", "multiple")
        
        if dividend_yield is not None:
            add_metric("Valuation", "dividendYield", "Dividend Yield", dividend_yield, "%", "percent")
            
        ev = None
        if not is_currency_mismatch and market_cap and total_debt is not None and total_cash is not None:
            ev = market_cap + total_debt - total_cash
            add_metric("Valuation", "enterpriseValue", "Enterprise Value", ev, "₹", "large_currency")
            if total_revenue and total_revenue > 0:
                add_metric("Valuation", "evToRevenue", "EV / Revenue", ev / total_revenue, "x", "multiple")
            if ebitda and ebitda > 0:
                add_metric("Valuation", "evToEbitda", "EV / EBITDA", ev / ebitda, "x", "multiple")

        # Growth
        if financials is not None and len(financials.columns) >= 2:
            prev_revenue = self._get_val(financials, "Total Revenue", 1)
            prev_eps = (self._get_val(financials, "Net Income", 1) / shares) if (self._get_val(financials, "Net Income", 1) and shares and not is_currency_mismatch) else None
            
            if total_revenue and prev_revenue and prev_revenue > 0:
                add_metric("Growth", "revenueGrowth", "Revenue Growth (YoY)", (total_revenue - prev_revenue) / prev_revenue, "%", "percent")
            if eps and prev_eps and prev_eps > 0:
                add_metric("Growth", "epsGrowth", "EPS Growth (YoY)", (eps - prev_eps) / prev_eps, "%", "percent")
                
        if financials is not None and len(financials.columns) >= 4:
            rev_3y = self._get_val(financials, "Total Revenue", 3)
            ni_3y = self._get_val(financials, "Net Income", 3)
            if total_revenue and rev_3y and rev_3y > 0:
                cagr_rev = self._compute_cagr(total_revenue, rev_3y, 3)
                add_metric("Growth", "revenueCagr3Y", "Revenue CAGR (3Y)", cagr_rev, "%", "percent")
            if net_income and ni_3y and ni_3y > 0:
                cagr_ni = self._compute_cagr(net_income, ni_3y, 3)
                add_metric("Growth", "netIncomeCagr3Y", "Net Income CAGR (3Y)", cagr_ni, "%", "percent")

        # Profitability
        if total_revenue and total_revenue > 0:
            if net_income: add_metric("Profitability", "netMargin", "Net Margin", net_income / total_revenue, "%", "percent")
            if ebitda: add_metric("Profitability", "ebitdaMargin", "EBITDA Margin", ebitda / total_revenue, "%", "percent")
        if net_income and equity and equity > 0:
            add_metric("Profitability", "roe", "Return on Equity (ROE)", net_income / equity, "%", "percent")
        if ebit and total_assets and current_liabilities:
            cap_emp = total_assets - current_liabilities
            if cap_emp > 0:
                add_metric("Profitability", "roce", "Return on Capital Employed (ROCE)", ebit / cap_emp, "%", "percent")

        # Financial Health
        if total_debt is not None and equity and equity > 0:
            add_metric("Financial Health", "debtToEquity", "Debt / Equity", total_debt / equity, "%", "percent")
        if total_debt is not None and total_cash is not None:
            add_metric("Financial Health", "netDebt", "Net Debt", total_debt - total_cash, "₹", "large_currency")

        return metrics

    def generate_intelligence_report(self, ticker_symbol: str, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Uses LLM to interpret metrics and provide a structured JSON report."""
        
        metrics_context = "\n".join([
            f"- {m['category']} | {m['label']}: {m['value']} {m['unit']} (Format: {m['format_rule']})"
            for m in metrics
        ])
        
        system_prompt = (
            "You are an expert financial analyst. Analyze the provided metrics for a company "
            "and output a strictly valid JSON object representing a 'Financial Intelligence Report'. "
            "Follow this JSON schema EXACTLY:\n"
            "{\n"
            "  \"overall_assessment\": \"string (e.g. 'Strong Business / Reasonable Valuation / Moderate Growth')\",\n"
            "  \"deep_analysis\": {\n"
            "    \"business_quality\": [\n"
            "        {\"metric\": \"string (e.g. 'ROE')\", \"value\": \"string (e.g. '45.9%')\", \"interpretation\": \"string (e.g. 'Excellent profitability')\"}\n"
            "    ],\n"
            "    \"valuation\": [\n"
            "        {\"metric\": \"string\", \"value\": \"string\", \"interpretation\": \"string\"}\n"
            "    ],\n"
            "    \"financial_strength\": [\"string\", \"string\"],\n"
            "    \"growth\": [\"string\", \"string\"],\n"
            "    \"risks\": [\"string\", \"string\"]\n"
            "  },\n"
            "  \"key_findings\": {\n"
            "    \"biggest_positive\": \"string\",\n"
            "    \"biggest_negative\": \"string\",\n"
            "    \"valuation_observation\": \"string\",\n"
            "    \"health_observation\": \"string\"\n"
            "  }\n"
            "}\n"
            "Provide insightful interpretations for metrics. Make your insights extremely analytical, referencing specific numbers. "
            "Do NOT output markdown code blocks. Output ONLY raw parseable JSON."
        )
        
        user_prompt = f"Company Ticker: {ticker_symbol}\n\nMetrics Data:\n{metrics_context}\n\nGenerate the JSON report."
        
        try:
            response = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1
            )
            raw_text = response.content.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```", "").strip()
            
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Failed to generate LLM intelligence report for {ticker_symbol}: {e}")
            return {
                "overall_assessment": "Analysis Unavailable",
                "deep_analysis": {
                    "business_quality": [],
                    "valuation": [],
                    "financial_strength": [],
                    "growth": [],
                    "risks": []
                },
                "key_findings": {
                    "biggest_positive": "N/A",
                    "biggest_negative": "N/A",
                    "valuation_observation": "N/A",
                    "health_observation": "N/A"
                }
            }
