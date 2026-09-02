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
        net_income = self._get_val(financials, "Net Income") or self._get_val(financials, "NetIncome")
        total_revenue = self._get_val(financials, "Total Revenue") or self._get_val(financials, "TotalRevenue")
        gross_profit = self._get_val(financials, "Gross Profit") or self._get_val(financials, "GrossProfit")
        operating_income = self._get_val(financials, "Operating Income") or self._get_val(financials, "OperatingIncome")
        ebitda = self._get_val(financials, "EBITDA") or self._get_val(financials, "Normalized EBITDA") or self._get_val(financials, "NormalizedEBITDA")
        ebit = self._get_val(financials, "EBIT") or operating_income
        interest_expense = self._get_val(financials, "Interest Expense") or self._get_val(financials, "InterestExpense")

        equity = self._get_val(balance_sheet, "Stockholders Equity") or self._get_val(balance_sheet, "StockholdersEquity") or self._get_val(balance_sheet, "Total Equity Gross Minority Interest") or self._get_val(balance_sheet, "TotalEquityGrossMinorityInterest")
        total_assets = self._get_val(balance_sheet, "Total Assets") or self._get_val(balance_sheet, "TotalAssets")
        current_assets = self._get_val(balance_sheet, "Current Assets") or self._get_val(balance_sheet, "CurrentAssets")
        current_liabilities = self._get_val(balance_sheet, "Current Liabilities") or self._get_val(balance_sheet, "CurrentLiabilities")
        inventory = self._get_val(balance_sheet, "Inventory") or 0.0
        total_debt = self._get_val(balance_sheet, "Total Debt") or self._get_val(balance_sheet, "TotalDebt")
        total_cash = self._get_val(balance_sheet, "Cash And Cash Equivalents") or self._get_val(balance_sheet, "CashAndCashEquivalents") or self._get_val(balance_sheet, "Cash Cash Equivalents And Short Term Investments") or self._get_val(balance_sheet, "CashCashEquivalentsAndShortTermInvestments")

        net_interest_income = self._get_val(financials, "Net Interest Income") or self._get_val(financials, "NetInterestIncome")

        price = getattr(fast_info, "last_price", None)
        market_cap = getattr(fast_info, "market_cap", None)
        shares = getattr(fast_info, "shares", None)
        year_high = getattr(fast_info, "year_high", None)
        year_low = getattr(fast_info, "year_low", None)
        day_open = getattr(fast_info, "open", None)
        prev_close = getattr(fast_info, "previous_close", None)
        volume = getattr(fast_info, "last_volume", None)

        def add_metric(category, key, label, value, unit="", format_rule="standard"):
            if value is not None:
                final_val = value * 100.0 if format_rule == "percent" else value
                metrics.append({
                    "category": category,
                    "key": key,
                    "label": label,
                    "value": round(final_val, 4) if isinstance(final_val, float) else final_val,
                    "unit": unit,
                    "format_rule": format_rule,
                    "source": "calculated"
                })

        # Market Snapshot
        add_metric("Market Snapshot", "currentPrice", "Current Price", price, "₹", "currency")
        add_metric("Market Snapshot", "marketCap", "Market Cap", market_cap, "₹", "large_currency")
        add_metric("Market Snapshot", "yearHigh", "52W High", year_high, "₹", "currency")
        add_metric("Market Snapshot", "yearLow", "52W Low", year_low, "₹", "currency")
        add_metric("Market Snapshot", "dayOpen", "Day Open", day_open, "₹", "currency")
        add_metric("Market Snapshot", "previousClose", "Previous Close", prev_close, "₹", "currency")
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

        if market_cap and total_revenue and total_revenue > 0:
            add_metric("Valuation", "priceToSales", "Price to Sales", market_cap / total_revenue, "x", "multiple")
            
        fcf = info.get("freeCashflow")
        if fcf:
            add_metric("Valuation", "freeCashFlow", "Free Cash Flow", fcf, "₹", "large_currency")
            if market_cap and fcf > 0:
                add_metric("Valuation", "priceToFcf", "Price to FCF", market_cap / fcf, "x", "multiple")

        ocf = info.get("operatingCashflow")
        if ocf:
            add_metric("Valuation", "operatingCashFlow", "Operating Cash Flow", ocf, "₹", "large_currency")

        # Growth
        if financials is not None and len(financials.columns) >= 2:
            prev_revenue = self._get_val(financials, "Total Revenue", 1) or self._get_val(financials, "TotalRevenue", 1)
            prev_eps = (self._get_val(financials, "Net Income", 1) / shares) if (self._get_val(financials, "Net Income", 1) and shares and not is_currency_mismatch) else None
            prev_ni = self._get_val(financials, "Net Income", 1) or self._get_val(financials, "NetIncome", 1)
            prev_oi = self._get_val(financials, "Operating Income", 1) or self._get_val(financials, "OperatingIncome", 1)
            
            if total_revenue and prev_revenue and prev_revenue > 0:
                add_metric("Growth", "revenueGrowth", "Revenue Growth (YoY)", (total_revenue - prev_revenue) / prev_revenue, "%", "percent")
            if eps and prev_eps and prev_eps > 0:
                add_metric("Growth", "epsGrowth", "EPS Growth (YoY)", (eps - prev_eps) / prev_eps, "%", "percent")
            if net_income and prev_ni and prev_ni > 0:
                add_metric("Growth", "netIncomeGrowth", "Net Income Growth (YoY)", (net_income - prev_ni) / prev_ni, "%", "percent")
            if operating_income and prev_oi and prev_oi > 0:
                add_metric("Growth", "operatingIncomeGrowth", "Operating Income Growth (YoY)", (operating_income - prev_oi) / prev_oi, "%", "percent")
                
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
            if gross_profit: add_metric("Profitability", "grossMargin", "Gross Margin", gross_profit / total_revenue, "%", "percent")
            if operating_income: add_metric("Profitability", "operatingMargin", "Operating Margin", operating_income / total_revenue, "%", "percent")
            if net_income: add_metric("Profitability", "netMargin", "Net Margin", net_income / total_revenue, "%", "percent")
            if ebitda: add_metric("Profitability", "ebitdaMargin", "EBITDA Margin", ebitda / total_revenue, "%", "percent")
            if fcf: add_metric("Profitability", "fcfMargin", "FCF Margin", fcf / total_revenue, "%", "percent")
            
        if net_interest_income and total_assets and total_assets > 0:
            add_metric("Profitability", "netInterestMargin", "Net Interest Margin (NIM)", net_interest_income / total_assets, "%", "percent")
            
        if net_income and equity and equity > 0:
            add_metric("Profitability", "roe", "Return on Equity (ROE)", net_income / equity, "%", "percent")
        if net_income and total_assets and total_assets > 0:
            add_metric("Profitability", "roa", "Return on Assets (ROA)", net_income / total_assets, "%", "percent")
        if ebit and total_assets and current_liabilities:
            cap_emp = total_assets - current_liabilities
            if cap_emp > 0:
                add_metric("Profitability", "roce", "Return on Capital Employed (ROCE)", ebit / cap_emp, "%", "percent")
        if operating_income and total_assets and current_liabilities and total_cash is not None:
            invested_capital = (total_assets - total_cash) - current_liabilities
            if invested_capital > 0:
                add_metric("Profitability", "roic", "Return on Invested Capital (ROIC)", operating_income / invested_capital, "%", "percent")

        # Financial Health
        if current_assets and current_liabilities and current_liabilities > 0:
            add_metric("Financial Health", "currentRatio", "Current Ratio", current_assets / current_liabilities, "x", "multiple")
            add_metric("Financial Health", "quickRatio", "Quick Ratio", (current_assets - inventory) / current_liabilities, "x", "multiple")
        if ebit and interest_expense and interest_expense > 0:
            add_metric("Financial Health", "interestCoverage", "Interest Coverage", ebit / interest_expense, "x", "multiple")
        if total_debt is not None and equity and equity > 0:
            add_metric("Financial Health", "debtToEquity", "Debt / Equity", total_debt / equity, "x", "multiple")
        if total_debt is not None and total_cash is not None:
            add_metric("Financial Health", "netDebt", "Net Debt", total_debt - total_cash, "₹", "large_currency")
        # Add all other Yahoo Query metrics as Supporting Metrics (excluding NaN)
        # 1. Financials
        if financials is not None and not financials.empty:
            for metric_name in financials.index:
                val = self._get_val(financials, metric_name, 0)
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    add_metric("Supporting Metrics", f"fin_{metric_name}", str(metric_name), val, "", "standard")
                    
        # 2. Balance Sheet
        if balance_sheet is not None and not balance_sheet.empty:
            for metric_name in balance_sheet.index:
                val = self._get_val(balance_sheet, metric_name, 0)
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    add_metric("Supporting Metrics", f"bs_{metric_name}", str(metric_name), val, "", "standard")
                    
        # 3. Info / Fast Info
        if info is not None:
            for metric_name, val in info.items():
                if val is not None and isinstance(val, (int, float)) and not (isinstance(val, float) and math.isnan(val)):
                    add_metric("Supporting Metrics", f"info_{metric_name}", str(metric_name), val, "", "standard")

        return metrics

    def _generate_fallback_findings(self, metrics: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate data-driven deterministic key findings from available metrics."""
        m_map: Dict[str, Any] = {}
        for m in metrics:
            k = (m.get("key") or m.get("label") or "").lower().replace("_", "").replace(" ", "")
            v = m.get("value")
            if k and v is not None and str(v).strip() not in ["N/A", "None", ""]:
                m_map[k] = (v, m.get("unit", ""), m.get("label", k))

        # 1. Biggest Positive
        positives = []
        for r_key in ["roe", "returnonequity"]:
            if r_key in m_map:
                try:
                    val_num = float(str(m_map[r_key][0]).replace("%", "").replace(",", ""))
                    if val_num > 15:
                        positives.append(f"Strong Return on Equity ({val_num:.1f}%) highlighting exceptional capital compounding.")
                except Exception:
                    pass
        for op_key in ["operatingmargin", "netmargin", "profitmargin"]:
            if op_key in m_map:
                try:
                    val_num = float(str(m_map[op_key][0]).replace("%", "").replace(",", ""))
                    if val_num > 12:
                        positives.append(f"Healthy operating profitability with operating margin of {val_num:.1f}%.")
                except Exception:
                    pass
        for d_key in ["debttoequity", "debt/equity"]:
            if d_key in m_map:
                try:
                    val_num = float(str(m_map[d_key][0]).replace("x", "").replace(",", ""))
                    if val_num < 0.6:
                        positives.append(f"Conservative balance sheet with low financial leverage (Debt/Equity of {val_num:.2f}x).")
                except Exception:
                    pass
        for g_key in ["revenuegrowth", "earningsgrowth"]:
            if g_key in m_map:
                try:
                    val_num = float(str(m_map[g_key][0]).replace("%", "").replace(",", ""))
                    if val_num > 10:
                        positives.append(f"Solid top-line momentum with revenue growth of {val_num:.1f}%.")
                except Exception:
                    pass
        if not positives:
            positives.append("Resilient core operational performance supported by stable financial foundations.")

        # 2. Biggest Negative
        negatives = []
        for pe_key in ["trailingpe", "forwardpe", "pe"]:
            if pe_key in m_map:
                try:
                    val_num = float(str(m_map[pe_key][0]).replace("x", "").replace(",", ""))
                    if val_num > 35:
                        negatives.append(f"Valuation multiple is rich with P/E at {val_num:.1f}x, leaving little room for earnings misses.")
                except Exception:
                    pass
        for pb_key in ["pricetobook", "pb"]:
            if pb_key in m_map:
                try:
                    val_num = float(str(m_map[pb_key][0]).replace("x", "").replace(",", ""))
                    if val_num > 8:
                        negatives.append(f"Elevated Price-to-Book multiple ({val_num:.1f}x) reflects high market expectations.")
                except Exception:
                    pass
        for d_key in ["debttoequity"]:
            if d_key in m_map:
                try:
                    val_num = float(str(m_map[d_key][0]).replace("x", "").replace(",", ""))
                    if val_num > 1.5:
                        negatives.append(f"Elevated financial leverage with Debt-to-Equity at {val_num:.2f}x.")
                except Exception:
                    pass
        if not negatives:
            negatives.append("Broader macroeconomic headwinds, cost inflation, and industry competition require ongoing monitoring.")

        # 3. Valuation Observation
        val_parts = []
        if "trailingpe" in m_map: val_parts.append(f"Trailing P/E of {m_map['trailingpe'][0]}x")
        if "forwardpe" in m_map: val_parts.append(f"Forward P/E of {m_map['forwardpe'][0]}x")
        if "pricetobook" in m_map: val_parts.append(f"P/B of {m_map['pricetobook'][0]}x")
        if "dividendyield" in m_map: val_parts.append(f"Dividend Yield of {m_map['dividendyield'][0]}%")
        val_sentence = f"The stock is trading at {', '.join(val_parts)}." if val_parts else "Current valuation multiples reflect market expectations relative to sector benchmarks."

        # 4. Health Observation
        health_parts = []
        if "debttoequity" in m_map: health_parts.append(f"Debt-to-Equity of {m_map['debttoequity'][0]}x")
        if "currentratio" in m_map: health_parts.append(f"Current Ratio of {m_map['currentratio'][0]}x")
        if "quickratio" in m_map: health_parts.append(f"Quick Ratio of {m_map['quickratio'][0]}x")
        health_sentence = f"Balance sheet demonstrates {', '.join(health_parts)}, indicating solid liquidity and solvency." if health_parts else "Capital structure exhibits stable liquidity coverage and manageable debt obligations."

        return {
            "biggest_positive": positives[0],
            "biggest_negative": negatives[0],
            "valuation_observation": val_sentence,
            "health_observation": health_sentence,
        }

    def generate_intelligence_report(self, ticker_symbol: str, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Uses LLM to interpret metrics and provide a structured JSON report."""
        
        fallback_kf = self._generate_fallback_findings(metrics)

        # Build comprehensive metrics context including both primary and supporting metrics
        context_lines = []
        for m in metrics:
            cat = m.get("category", "Metrics")
            label = m.get("label", "")
            if label.startswith(("fin_", "bs_", "info_")):
                label = label.split("_", 1)[1]
            val = m.get("value")
            unit = m.get("unit", "")
            if val is not None and str(val).strip() not in ["N/A", "None", ""]:
                context_lines.append(f"- [{cat}] {label}: {val} {unit}".strip())
            
        metrics_context = "\n".join(context_lines)
        
        system_prompt = (
            "You are an expert financial analyst. Analyze the provided metrics for a company "
            "and output a strictly valid JSON object representing a 'Financial Intelligence Report'. "
            "Follow this JSON schema EXACTLY:\n"
            "{\n"
            "  \"overall_assessment\": \"string (e.g. 'Strong Business / Reasonable Valuation / Moderate Growth')\",\n"
            "  \"deep_analysis\": {\n"
            "    \"business_quality\": [\n"
            "        {\"metric\": \"string (e.g. 'ROE')\", \"value\": \"string (e.g. '45.9%')\", \"interpretation\": \"string (e.g. 'Excellent profitability')\", \"status\": \"good\" | \"moderate\" | \"bad\"}\n"
            "    ],\n"
            "    \"valuation\": [\n"
            "        {\"metric\": \"string\", \"value\": \"string\", \"interpretation\": \"string\", \"status\": \"good\" | \"moderate\" | \"bad\"}\n"
            "    ],\n"
            "    \"financial_strength\": [\n"
            "        {\"metric\": \"string\", \"value\": \"string\", \"interpretation\": \"string\", \"status\": \"good\" | \"moderate\" | \"bad\"}\n"
            "    ],\n"
            "    \"growth\": [\n"
            "        {\"metric\": \"string\", \"value\": \"string\", \"interpretation\": \"string\", \"status\": \"good\" | \"moderate\" | \"bad\"}\n"
            "    ],\n"
            "    \"risks\": [\n"
            "        {\"metric\": \"string\", \"value\": \"string\", \"interpretation\": \"string\", \"status\": \"bad\"}\n"
            "    ]\n"
            "  },\n"
            "  \"key_findings\": {\n"
            "    \"biggest_positive\": \"string (Concise analytical sentence highlighting the single biggest strength/positive catalyst)\",\n"
            "    \"biggest_negative\": \"string (Concise analytical sentence highlighting the key risk, headwind, or weakness)\",\n"
            "    \"valuation_observation\": \"string (Concise observation on current valuation, multiples, and pricing context)\",\n"
            "    \"health_observation\": \"string (Concise assessment of balance sheet health, debt coverage, liquidity, and solvency)\"\n"
            "  }\n"
            "}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Synthesize insights from BOTH high-level ratios and supporting financial/balance sheet metrics provided.\n"
            "2. Ensure all four fields in `key_findings` (`biggest_positive`, `biggest_negative`, `valuation_observation`, `health_observation`) are populated with clear, concrete analytical sentences.\n"
            "3. Do NOT equate EBITDA directly to free cash flow. EBITDA represents operating profitability before interest, taxes, depreciation, and amortization.\n"
            "4. Do NOT evaluate margins in a vacuum; consider business model and capital structure.\n"
            "5. Debt/Equity ratios under 1.0x (and especially under 0.5x) indicate low leverage or a strong net cash position.\n"
            "6. **STRICTLY USE ONLY THE METRICS PROVIDED IN THE PROMPT.** Do NOT invent external financial figures.\n"
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
            
            parsed = json.loads(raw_text)
            
            # Normalize key_findings and fill any missing or N/A fields from fallback_kf
            kf = parsed.get("key_findings", {})
            invalid_phrases = ["n/a", "no data", "none", "not available", "unavailable", "no positive", "no negative", "no valuation", "no financial", "no metrics"]
            if isinstance(kf, dict):
                def _val_or_fallback(field: str, aliases: List[str]) -> str:
                    for a in [field] + aliases:
                        v = kf.get(a)
                        if v and isinstance(v, str):
                            clean = v.strip()
                            if not any(ip in clean.lower() for ip in invalid_phrases) and len(clean) > 10:
                                return clean
                    return fallback_kf.get(field, "N/A")

                normalized_kf = {
                    "biggest_positive": _val_or_fallback("biggest_positive", ["positive", "biggest_positives"]),
                    "biggest_negative": _val_or_fallback("biggest_negative", ["negative", "biggest_negatives"]),
                    "valuation_observation": _val_or_fallback("valuation_observation", ["valuation", "valuation_summary"]),
                    "health_observation": _val_or_fallback("health_observation", ["financial_health", "health", "health_summary"]),
                }
                parsed["key_findings"] = normalized_kf
            elif isinstance(kf, list) and len(kf) >= 4:
                def _item_or_fallback(val: Any, field: str) -> str:
                    if val and isinstance(val, str):
                        clean = val.strip()
                        if not any(ip in clean.lower() for ip in invalid_phrases) and len(clean) > 10:
                            return clean
                    return fallback_kf.get(field, "N/A")

                parsed["key_findings"] = {
                    "biggest_positive": _item_or_fallback(kf[0], "biggest_positive"),
                    "biggest_negative": _item_or_fallback(kf[1], "biggest_negative"),
                    "valuation_observation": _item_or_fallback(kf[2], "valuation_observation"),
                    "health_observation": _item_or_fallback(kf[3], "health_observation"),
                }
            else:
                parsed["key_findings"] = fallback_kf
            
            return parsed
        except Exception as e:
            logger.error(f"Failed to generate LLM intelligence report for {ticker_symbol}: {e}")
            return {
                "overall_assessment": "Comprehensive Financial Assessment",
                "deep_analysis": {
                    "business_quality": [],
                    "valuation": [],
                    "financial_strength": [],
                    "growth": [],
                    "risks": []
                },
                "key_findings": fallback_kf
            }

    def extract_agent_data(self, ticker_symbol: str, fast_info: Any, financials: Any, balance_sheet: Any) -> Dict[str, Any]:
        from app.schemas import AgentCurrent, AgentValuation, AgentFinancialYear, AgentHealth, AgentFinancialData
        import datetime
        
        price = getattr(fast_info, "last_price", None)
        if price is None: price = 0.0
        currency = getattr(fast_info, "currency", "USD")
        market_cap = getattr(fast_info, "market_cap", None)
        day_high = getattr(fast_info, "year_high", None)  # Fallback to 52w high if day high missing
        day_low = getattr(fast_info, "year_low", None)
        prev_close = getattr(fast_info, "previous_close", None)
        
        change = None
        change_percent = None
        if price is not None and prev_close is not None and prev_close > 0:
            change = price - prev_close
            change_percent = (change / prev_close) * 100.0

        current = AgentCurrent(
            price=price or 0.0,
            currency=currency,
            change=change,
            change_percent=change_percent,
            marketCap=market_cap,
            dayOpen=getattr(fast_info, "open", None),
            dayHigh=day_high,
            dayLow=day_low,
            previousClose=prev_close,
            fiftyTwoWeekHigh=getattr(fast_info, "year_high", None),
            fiftyTwoWeekLow=getattr(fast_info, "year_low", None),
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        
        # Valuation
        pe = None
        shares = getattr(fast_info, "shares", None)
        net_income_ttm = self._get_val(financials, "Net Income", 0)
        eps = None
        if net_income_ttm and shares:
            eps = net_income_ttm / shares
        if price and eps and eps > 0:
            pe = price / eps
            
        equity = self._get_val(balance_sheet, "Stockholders Equity", 0) or self._get_val(balance_sheet, "Common Stock Equity", 0) or self._get_val(balance_sheet, "Total Equity Gross Minority Interest", 0)
        pb = None
        if market_cap and equity and equity > 0:
            pb = market_cap / equity
            
        total_debt = self._get_val(balance_sheet, "Total Debt", 0)
        total_cash = self._get_val(balance_sheet, "Cash And Cash Equivalents", 0) or self._get_val(balance_sheet, "Cash Cash Equivalents And Short Term Investments", 0)
        ev = None
        if market_cap and total_debt is not None and total_cash is not None:
            ev = market_cap + total_debt - total_cash
            
        valuation = AgentValuation(
            forwardPE=pe,
            trailingPE=pe,
            priceToBook=pb,
            enterpriseValue=ev
        )
        
        # Health
        net_debt = None
        if total_debt is not None and total_cash is not None:
            net_debt = total_debt - total_cash
        debt_to_equity = None
        if total_debt is not None and equity and equity > 0:
            debt_to_equity = total_debt / equity
            
        current_assets = self._get_val(balance_sheet, "Current Assets", 0)
        current_liabilities = self._get_val(balance_sheet, "Current Liabilities", 0)
        current_ratio = None
        if current_assets and current_liabilities and current_liabilities > 0:
            current_ratio = current_assets / current_liabilities
            
        health = AgentHealth(
            totalDebt=total_debt,
            cash=total_cash,
            netDebt=net_debt,
            debtToEquity=debt_to_equity,
            currentRatio=current_ratio
        )
        
        # Financials
        fin_list = []
        if financials is not None and not financials.empty:
            num_years = min(4, len(financials.columns))
            for i in range(num_years - 1, -1, -1):
                rev = self._get_val(financials, "Total Revenue", i)
                ni = self._get_val(financials, "Net Income", i)
                ebitda = self._get_val(financials, "EBITDA", i) or self._get_val(financials, "Normalized EBITDA", i)
                op_margin = None
                if ebitda and rev and rev > 0:
                    op_margin = ebitda / rev
                e_eps = None
                if ni and shares:
                    e_eps = ni / shares
                
                try:
                    # Parse year from timestamp
                    col_name = financials.columns[i]
                    if isinstance(col_name, str):
                        year = int(col_name[:4])
                    elif hasattr(col_name, "year"):
                        year = col_name.year
                    else:
                        year = 2024 - i
                except:
                    year = 2024 - i
                    
                fin_list.append(AgentFinancialYear(
                    year=year,
                    revenue=rev,
                    netIncome=ni,
                    eps=e_eps,
                    operatingMargin=op_margin
                ))
                
        agent_data = AgentFinancialData(
            company=ticker_symbol,
            current=current,
            valuation=valuation,
            financials=fin_list,
            health=health
        )
        
        return agent_data.model_dump()

