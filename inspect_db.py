from app.db.database import SessionLocal
from app.models import PortfolioAnalysis
import json

db = SessionLocal()
report = db.query(PortfolioAnalysis).order_by(PortfolioAnalysis.created_at.desc()).first()

if report:
    print("Report ID:", report.id)
    print("Created At:", report.created_at)
    print("Holdings:", json.dumps(report.holdings, indent=2))
    print("Metrics:", json.dumps(report.portfolio_metrics, indent=2))
else:
    print("No reports found.")
