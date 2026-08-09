"""
Portfolio Analyzer REST API Endpoints.
Accepts in-memory portfolio.csv uploads, delegates to PortfolioAgent, and persists reports for authenticated users.
"""

import io
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import pandas as pd
from sqlalchemy.orm import Session

from app.agents.portfolio_agent import PortfolioAgent
from app.dependencies import get_db, get_optional_user, get_current_user
from app.models import User
from app.repositories import PortfolioAnalysisRepository
from app.schemas import (
    HoldingInput,
    PortfolioAnalysisResponse,
    PortfolioMetrics,
    AllocationBreakdown,
    HoldingAnalysis,
    BenchmarkComparison,
    TaxLossHarvestingAlert,
)
from app.utils import get_logger

logger = get_logger("finnai.api.portfolio_analyzer")

router = APIRouter(prefix="/portfolio", tags=["Portfolio Analyzer"])


def parse_portfolio_file_in_memory(filename: str, contents: bytes) -> List[HoldingInput]:
    """
    Parse uploaded CSV/Excel file content in-memory.
    Robust against broker exports (e.g. Zerodha) with preamble lines and multiple tables.
    """
    dfs = []
    if filename.lower().endswith(('.xlsx', '.xls')):
        try:
            excel_data = pd.read_excel(io.BytesIO(contents), sheet_name=None, header=None, dtype=str)
            combined_key = next((k for k in excel_data.keys() if 'combined' in k.lower()), None)
            if combined_key:
                dfs = [excel_data[combined_key]]
            else:
                dfs = list(excel_data.values())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse Excel file: {e}"
            )
    else:
        try:
            text = contents.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = contents.decode("latin-1")
            
        try:
            import csv
            lines = text.strip().split('\n')
            # Detect delimiter: if there are more tabs than commas in the first 10 lines, it's tab-separated
            delimiter = '\t' if sum(l.count('\t') for l in lines[:10]) > sum(l.count(',') for l in lines[:10]) else ','
            
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
            if rows:
                max_cols = max(len(r) for r in rows)
                padded_rows = [r + [''] * (max_cols - len(r)) for r in rows]
                dfs = [pd.DataFrame(padded_rows)]
            else:
                dfs = []
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV file: {e}"
            )

    holdings_dict = {}

    for df in dfs:
        sym_col, qty_col, price_col, name_col, date_col = -1, -1, -1, -1, -1
        
        for idx, row in df.iterrows():
            row_vals = [str(x).strip().lower() if pd.notna(x) else '' for x in row.values]
            
            # Identify header row
            if sym_col == -1:
                s_idx = next((i for i, v in enumerate(row_vals) if v in ['symbol', 'ticker', 'code', 'stock', 'company', 'instrument']), -1)
                q_idx = next((i for i, v in enumerate(row_vals) if v in ['quantity', 'qty', 'shares', 'units'] or 'quantity available' in v or 'quantity' in v), -1)
                p_idx = next((i for i, v in enumerate(row_vals) if 'price' in v or 'avg' in v or 'cost' in v), -1)
                
                if s_idx != -1 and q_idx != -1 and p_idx != -1:
                    sym_col, qty_col, price_col = s_idx, q_idx, p_idx
                    name_col = next((i for i, v in enumerate(row_vals) if v in ['name', 'company_name', 'title']), -1)
                    date_col = next((i for i, v in enumerate(row_vals) if 'date' in v), -1)
                continue
            
            # Read data row
            raw_sym = str(row.values[sym_col]).strip() if pd.notna(row.values[sym_col]) else ''
            
            if not raw_sym or raw_sym.lower() in ['nan', 'none', 'null', '']:
                if all(v == '' for v in row_vals):
                    sym_col = -1 # Reset to find next table block
                continue
                
            try:
                qty_str = str(row.values[qty_col]).strip().replace(',', '')
                qty = float(qty_str)
                price_str = str(row.values[price_col]).strip().replace(',', '')
                price = float(price_str)
            except (ValueError, TypeError, IndexError):
                continue
                
            if qty <= 0 or price <= 0:
                continue
                
            name_val = str(row.values[name_col]).strip() if name_col != -1 and pd.notna(row.values[name_col]) else None
            date_val = str(row.values[date_col]).strip() if date_col != -1 and pd.notna(row.values[date_col]) else None
            
            # Deduplication across sheets
            sym_key = raw_sym.upper()
            if sym_key in holdings_dict:
                existing = holdings_dict[sym_key]
                if existing.quantity == qty and existing.avg_buy_price == price:
                    pass # exact duplicate
                else:
                    total_qty = existing.quantity + qty
                    total_cost = (existing.quantity * existing.avg_buy_price) + (qty * price)
                    existing.quantity = total_qty
                    existing.avg_buy_price = total_cost / total_qty
            else:
                holdings_dict[sym_key] = HoldingInput(
                    symbol=raw_sym,
                    name=name_val,
                    quantity=qty,
                    avg_buy_price=price,
                    date_acquired=date_val
                )

    if not holdings_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid holding rows found in uploaded file. Ensure columns include Symbol, Quantity, and Price."
        )

    return list(holdings_dict.values())


@router.post("/analyze", response_model=PortfolioAnalysisResponse, summary="Analyze uploaded portfolio file")
async def analyze_portfolio_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
) -> PortfolioAnalysisResponse:
    """
    Accepts multipart/form-data CSV/Excel upload, parses in-memory, executes PortfolioAgent analysis,
    and persists report for authenticated users (capped at 10 FIFO).
    """
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid .csv, .xlsx, or .xls file."
        )

    contents = await file.read()
    holdings_input = parse_portfolio_file_in_memory(file.filename, contents)

    agent = PortfolioAgent(db=db)

    try:
        analysis_result = agent.analyze_portfolio(holdings_input)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Portfolio analysis failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during portfolio analysis: {exc}"
        )

    # Persist report for authenticated user (capped at 10 FIFO)
    if current_user:
        repo = PortfolioAnalysisRepository(db)
        db_obj = repo.save_analysis(user_id=current_user.id, analysis=analysis_result)
        analysis_result.id = db_obj.id
        analysis_result.created_at = db_obj.created_at.isoformat()

    return analysis_result


@router.get("/analyses", response_model=List[PortfolioAnalysisResponse], summary="List saved portfolio analysis for authenticated user")
def list_saved_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PortfolioAnalysisResponse]:
    """
    Retrieves the saved portfolio analysis report for the authenticated user (max 1 portfolio).
    """
    repo = PortfolioAnalysisRepository(db)
    records = repo.get_user_analyses(user_id=current_user.id)

    results = []
    for r in records:
        results.append(
            PortfolioAnalysisResponse(
                id=r.id,
                summary=r.summary,
                holdings=[HoldingAnalysis.model_validate(h) for h in r.holdings],
                portfolio_metrics=PortfolioMetrics.model_validate(r.portfolio_metrics),
                allocation=AllocationBreakdown.model_validate(r.allocation),
                rebalancing_suggestions=r.rebalancing_suggestions or [],
                news_alerts=r.news_alerts or {},
                red_flags=r.red_flags or [],
                benchmark_comparison=[BenchmarkComparison.model_validate(b) for b in (r.benchmark_comparison or [])],
                tax_loss_harvesting=[TaxLossHarvestingAlert.model_validate(t) for t in (r.tax_loss_harvesting or [])],
                images=r.images or [],
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
        )
    return results


@router.get("/analyses/{analysis_id}", response_model=PortfolioAnalysisResponse, summary="Get saved portfolio analysis by ID")
def get_saved_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioAnalysisResponse:
    """
    Retrieves a specific saved analysis report for the authenticated user.
    """
    repo = PortfolioAnalysisRepository(db)
    record = repo.get_analysis_by_id(analysis_id=analysis_id, user_id=current_user.id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved analysis with ID {analysis_id} not found."
        )

    return PortfolioAnalysisResponse(
        id=record.id,
        summary=record.summary,
        holdings=[HoldingAnalysis.model_validate(h) for h in record.holdings],
        portfolio_metrics=PortfolioMetrics.model_validate(record.portfolio_metrics),
        allocation=AllocationBreakdown.model_validate(record.allocation),
        rebalancing_suggestions=record.rebalancing_suggestions or [],
        news_alerts=record.news_alerts or {},
        red_flags=record.red_flags or [],
        benchmark_comparison=[BenchmarkComparison.model_validate(b) for b in (record.benchmark_comparison or [])],
        tax_loss_harvesting=[TaxLossHarvestingAlert.model_validate(t) for t in (record.tax_loss_harvesting or [])],
        images=record.images or [],
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.delete("/analyses/{analysis_id}", summary="Delete saved portfolio analysis by ID")
def delete_saved_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Deletes a saved analysis report for the authenticated user.
    """
    repo = PortfolioAnalysisRepository(db)
    success = repo.delete_analysis(analysis_id=analysis_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found or permission denied."
        )
    return {"status": "success", "message": f"Saved analysis {analysis_id} deleted successfully."}
