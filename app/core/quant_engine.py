"""
Quant Engine for FinnAI Platform.
Pure Python mathematical financial calculators.
Zero LLM calls, zero external API requests.
Includes safe mathematical handling for division-by-zero, negative bases, and missing values.
"""

import math
from typing import Any, Dict, Optional

from app.schemas import (
    DividendMetrics,
    EfficiencyRatios,
    GrowthMetrics,
    LeverageRatios,
    ProfitabilityRatios,
    RatioSnapshot,
    ValuationRatios,
)
from app.utils import get_logger

logger = get_logger("finnai.quant_engine")


class QuantEngine:
    """
    Pure Python quantitative mathematical calculations engine.
    Calculates financial ratios, valuation multiples, CAGR growth rates, and leverage statistics.
    """

    @staticmethod
    def safe_divide(numerator: Any, denominator: Any) -> Optional[float]:
        """
        Safely divide two numbers handling None, zero denominators, and NaN/Inf values.

        Returns:
            Float rounded to 4 decimal places, or None if calculation is invalid.
        """
        if numerator is None or denominator is None:
            return None

        try:
            num = float(numerator)
            den = float(denominator)

            if den == 0.0 or math.isnan(num) or math.isnan(den) or math.isinf(num) or math.isinf(den):
                return None

            result = num / den
            if math.isnan(result) or math.isinf(result):
                return None

            return round(result, 4)

        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def calc_cagr(start_value: Any, end_value: Any, years: int) -> Optional[float]:
        """
        Calculate Compound Annual Growth Rate (CAGR).
        Formula: (end_value / start_value) ** (1 / years) - 1

        Returns:
            CAGR float percentage (e.g. 0.1524 for 15.24%), or None if non-calculable.
        """
        if start_value is None or end_value is None or years <= 0:
            return None

        try:
            start_val = float(start_value)
            end_val = float(end_value)

            # CAGR is undefined or invalid for negative or zero starting values
            if start_val <= 0.0 or end_val <= 0.0:
                return None

            ratio = end_val / start_val
            cagr = (ratio ** (1.0 / float(years))) - 1.0

            if math.isnan(cagr) or math.isinf(cagr):
                return None

            return round(cagr, 4)

        except (ValueError, TypeError, ZeroDivisionError, OverflowError):
            return None

    @staticmethod
    def calc_yoy_growth(current_val: Any, previous_val: Any) -> Optional[float]:
        """
        Calculate Year-over-Year growth percentage.
        Formula: (current_val - previous_val) / abs(previous_val)
        """
        if current_val is None or previous_val is None:
            return None

        try:
            curr = float(current_val)
            prev = float(previous_val)

            if prev == 0.0:
                return None

            growth = (curr - prev) / abs(prev)
            if math.isnan(growth) or math.isinf(growth):
                return None

            return round(growth, 4)

        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @classmethod
    def calc_profitability(cls, data: Dict[str, Any]) -> ProfitabilityRatios:
        """
        Calculate profitability and margin ratios.
        """
        roe = data.get("roe")
        if roe is None:
            roe = cls.safe_divide(data.get("net_income"), data.get("total_equity"))

        roa = cls.safe_divide(data.get("net_income"), data.get("total_assets"))

        # Use pre-computed ROCE if available, otherwise calculate from components
        roce = data.get("roce")
        if roce is None:
            ebit = data.get("ebit") or data.get("operating_income")
            capital_employed = (
                data.get("capital_employed")
                or (float(data.get("total_assets", 0) or 0) - float(data.get("current_liabilities", 0) or 0))
                if data.get("total_assets") and data.get("current_liabilities")
                else None
            )
            roce = cls.safe_divide(ebit, capital_employed)

        gross_margin = data.get("gross_margins")
        if gross_margin is None:
            gross_margin = cls.safe_divide(data.get("gross_profit"), data.get("revenue"))

        operating_margin = cls.safe_divide(
            data.get("operating_income") or data.get("ebit"), data.get("revenue")
        )

        net_margin = data.get("profit_margins")
        if net_margin is None:
            net_margin = cls.safe_divide(data.get("net_income"), data.get("revenue"))

        return ProfitabilityRatios(
            roe=roe,
            roa=roa,
            roce=roce,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_profit_margin=net_margin,
        )

    @classmethod
    def calc_valuation(cls, data: Dict[str, Any]) -> ValuationRatios:
        """
        Calculate valuation ratios and price multiples.
        """
        pe = data.get("pe_ratio")
        if pe is None:
            pe = cls.safe_divide(data.get("price"), data.get("eps"))

        forward_pe = data.get("forward_pe")

        # Use pre-computed P/B if available, otherwise calculate
        pb = data.get("pb_ratio")
        if pb is None:
            pb = cls.safe_divide(data.get("price"), data.get("book_value_per_share"))

        peg = data.get("peg_ratio")
        if peg is None and pe and data.get("eps_growth_yoy"):
            eps_g = float(data.get("eps_growth_yoy", 0)) * 100.0
            peg = cls.safe_divide(pe, eps_g)

        ev_ebitda = data.get("ev_to_ebitda")
        if ev_ebitda is None:
            ev_ebitda = cls.safe_divide(data.get("enterprise_value"), data.get("ebitda"))

        return ValuationRatios(
            pe_ratio=pe,
            forward_pe=forward_pe,
            pb_ratio=pb,
            peg_ratio=peg,
            ev_to_ebitda=ev_ebitda,
        )

    @classmethod
    def calc_growth(cls, data: Dict[str, Any]) -> GrowthMetrics:
        """
        Calculate historical CAGR (3yr, 5yr) and YoY growth metrics.
        """
        rev_3y = cls.calc_cagr(data.get("revenue_3y_ago"), data.get("revenue_current"), 3)
        rev_5y = cls.calc_cagr(data.get("revenue_5y_ago"), data.get("revenue_current"), 5)

        eps_3y = cls.calc_cagr(data.get("eps_3y_ago"), data.get("eps_current"), 3)
        eps_5y = cls.calc_cagr(data.get("eps_5y_ago"), data.get("eps_current"), 5)

        rev_yoy = cls.calc_yoy_growth(data.get("revenue_current"), data.get("revenue_prev_year"))
        eps_yoy = cls.calc_yoy_growth(data.get("eps_current"), data.get("eps_prev_year"))

        return GrowthMetrics(
            revenue_cagr_3yr=rev_3y,
            revenue_cagr_5yr=rev_5y,
            eps_cagr_3yr=eps_3y,
            eps_cagr_5yr=eps_5y,
            revenue_growth_yoy=rev_yoy,
            eps_growth_yoy=eps_yoy,
        )

    @classmethod
    def calc_leverage(cls, data: Dict[str, Any]) -> LeverageRatios:
        """
        Calculate leverage, solvency, and liquidity ratios.
        """
        dte = data.get("debt_to_equity")
        if dte is None:
            dte = cls.safe_divide(data.get("total_debt"), data.get("total_equity"))

        current_ratio = data.get("current_ratio")
        if current_ratio is None:
            current_ratio = cls.safe_divide(data.get("current_assets"), data.get("current_liabilities"))

        quick_ratio = cls.safe_divide(
            (float(data.get("current_assets", 0) or 0) - float(data.get("inventory", 0) or 0))
            if data.get("current_assets") and data.get("inventory") is not None
            else None,
            data.get("current_liabilities"),
        )

        interest_cov = cls.safe_divide(
            data.get("ebit") or data.get("operating_income"), data.get("interest_expense")
        )

        return LeverageRatios(
            debt_to_equity=dte,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            interest_coverage=interest_cov,
        )

    @classmethod
    def calc_efficiency(cls, data: Dict[str, Any]) -> EfficiencyRatios:
        """
        Calculate asset turnover and operational efficiency ratios.
        """
        asset_turnover = cls.safe_divide(data.get("revenue"), data.get("total_assets"))
        inv_turnover = cls.safe_divide(data.get("cogs"), data.get("inventory"))

        return EfficiencyRatios(
            asset_turnover=asset_turnover,
            inventory_turnover=inv_turnover,
        )

    @classmethod
    def calc_dividend(cls, data: Dict[str, Any]) -> DividendMetrics:
        """
        Calculate dividend yield and payout ratio.
        """
        div_yield = data.get("dividend_yield")
        if div_yield is None:
            div_yield = cls.safe_divide(data.get("dividend_per_share"), data.get("price"))

        payout = cls.safe_divide(data.get("dividend_per_share"), data.get("eps"))

        return DividendMetrics(
            dividend_yield=div_yield,
            payout_ratio=payout,
        )

    @classmethod
    def compute_full_snapshot(
        cls, canonical_symbol: str, ticker_symbol: str, raw_data: Dict[str, Any]
    ) -> RatioSnapshot:
        """
        Compute full quantitative ratio snapshot across all financial categories.
        """
        return RatioSnapshot(
            symbol=ticker_symbol,
            canonical_symbol=canonical_symbol,
            profitability=cls.calc_profitability(raw_data),
            valuation=cls.calc_valuation(raw_data),
            growth=cls.calc_growth(raw_data),
            leverage=cls.calc_leverage(raw_data),
            efficiency=cls.calc_efficiency(raw_data),
            dividend=cls.calc_dividend(raw_data),
        )
