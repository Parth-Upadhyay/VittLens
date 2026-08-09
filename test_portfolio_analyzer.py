"""
Integration & Unit Test Suite for Portfolio Analyzer Feature.
Tests:
1. Universe JSON loading and validation.
2. In-memory CSV parsing.
3. PortfolioAgent risk and allocation metric calculations.
4. Repository FIFO 10-analysis cap.
"""

import os
import io
import unittest
from app.db.database import SessionLocal, Base, engine
from app.models import User
from app.schemas import HoldingInput
from app.agents.portfolio_agent import PortfolioAgent
from app.api.v1.endpoints.portfolio_analyzer import parse_portfolio_file_in_memory
from app.repositories import PortfolioAnalysisRepository
from app.schemas import (
    PortfolioAnalysisResponse,
    PortfolioMetrics,
    AllocationBreakdown,
    HoldingAnalysis,
)


def test_universe_loading():
    agent = PortfolioAgent()
    assert "stocks" in agent.universe
    assert "etfs" in agent.universe
    assert "mutual_funds" in agent.universe
    assert "RELIANCE" in agent.universe["stocks"]
    assert "NIFTYBEES" in agent.universe["etfs"]


def test_csv_parsing():
    csv_bytes = b"symbol,quantity,avg_buy_price\nRELIANCE,10,2450.00\nTCS,5,3800.00\nNIFTYBEES,100,260.00\n"
    holdings = parse_portfolio_file_in_memory("portfolio.csv", csv_bytes)
    assert len(holdings) == 3
    assert holdings[0].symbol == "RELIANCE"
    assert holdings[0].quantity == 10.0
    assert holdings[0].avg_buy_price == 2450.00


def test_portfolio_agent_metrics():
    agent = PortfolioAgent()
    holdings = [
        HoldingInput(symbol="RELIANCE", quantity=10, avg_buy_price=2450.0),
        HoldingInput(symbol="TCS", quantity=5, avg_buy_price=5000.0), # loss holding for tax loss harvesting test
        HoldingInput(symbol="NIFTYBEES", quantity=100, avg_buy_price=260.0),
    ]

    report = agent.analyze_portfolio(holdings)
    assert report.portfolio_metrics.total_invested > 0
    assert report.portfolio_metrics.total_value > 0
    assert 1 <= report.portfolio_metrics.risk_score <= 10
    assert len(report.holdings) == 3
    assert len(report.benchmark_comparison) == 3 # 1M, 6M, 1Y
    assert len(report.tax_loss_harvesting) >= 1 # TCS loss holding harvested


def test_repository_single_portfolio_limit():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_portfolio_user@example.com").first()
        if not user:
            user = User(
                email="test_portfolio_user@example.com",
                name="Portfolio Test User",
                provider="google",
                provider_user_id="test_user_123"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        repo = PortfolioAnalysisRepository(db)

        sample_response = PortfolioAnalysisResponse(
            summary="Test summary",
            holdings=[
                HoldingAnalysis(
                    symbol="RELIANCE",
                    name="Reliance Industries Ltd",
                    asset_type="stock",
                    quantity=10,
                    avg_buy_price=2450.0,
                    current_price=2500.0,
                    total_invested=24500.0,
                    current_value=25000.0,
                    pnl=500.0,
                    pnl_percent=2.04,
                    day_change=10.0,
                    weight_percent=100.0,
                    sector="Oil & Gas",
                )
            ],
            portfolio_metrics=PortfolioMetrics(
                total_value=25000.0,
                total_invested=24500.0,
                total_pnl=500.0,
                total_pnl_percent=2.04,
                day_pnl=100.0,
                risk_score=5,
                concentration_risk_percent=100.0,
            ),
            allocation=AllocationBreakdown(
                sector_breakdown={"Oil & Gas": 100.0},
                asset_type_breakdown={"stock": 100.0},
            ),
            rebalancing_suggestions=["Diversify into other sectors"],
            news_alerts={},
            red_flags=["High concentration risk"],
        )

        # Save 3 analyses sequentially
        for i in range(3):
            repo.save_analysis(user.id, sample_response)

        saved_list = repo.get_user_analyses(user.id)
        assert len(saved_list) == 1, f"Expected exactly 1 saved portfolio for user, got {len(saved_list)}"

    finally:
        db.close()


if __name__ == "__main__":
    print("Running test_universe_loading()...")
    test_universe_loading()
    print("[OK] test_universe_loading passed!")

    print("Running test_csv_parsing()...")
    test_csv_parsing()
    print("[OK] test_csv_parsing passed!")

    print("Running test_portfolio_agent_metrics()...")
    test_portfolio_agent_metrics()
    print("[OK] test_portfolio_agent_metrics passed!")

    print("Running test_repository_single_portfolio_limit()...")
    test_repository_single_portfolio_limit()
    print("[OK] test_repository_single_portfolio_limit passed!")

    print("\nALL PORTFOLIO ANALYZER INTEGRATION TESTS PASSED PERFECTLY!")
