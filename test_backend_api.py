"""
Standalone End-to-End Test & Verification Script for FastAPI Backend (OAuth, Guest Mode, & Chat endpoints).

Usage:
    python test_backend_api.py

Verifies:
1. Health check GET /api/v1/health
2. Guest Purpose of Visit submission POST /api/v1/auth/guest/purpose
3. Guest Mode query limit enforcement (3 queries allowed, 4th request returns 403 Forbidden)
4. Authenticated Bearer JWT chat request bypassing guest query limits
"""

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from app.auth import create_access_token
from app.db.database import SessionLocal, init_db
from app.main import app
from app.models import User
from app.utils import get_logger

logger = get_logger("finnai.test_backend_api", "INFO")


def test_backend_api() -> None:
    load_dotenv()
    init_db()

    client = TestClient(app)
    print("\n" + "=" * 70)
    print("--- 1. Testing GET /api/v1/health ---")
    print("=" * 70)

    res_health = client.get("/api/v1/health")
    print(f"Health Check Status Code: {res_health.status_code}")
    print(f"Response: {res_health.json()}")
    assert res_health.status_code == 200, "Health check failed!"

    print("\n" + "=" * 70)
    print("--- 2. Testing Guest Purpose of Visit (POST /api/v1/auth/guest/purpose) ---")
    print("=" * 70)

    res_purpose = client.post("/api/v1/auth/guest/purpose", json={"purpose_of_visit": "Retail Investor"})
    print(f"Guest Purpose Status Code: {res_purpose.status_code}")
    print(f"Response: {res_purpose.json()}")
    assert res_purpose.status_code == 200, "Guest purpose submission failed!"

    print("\n" + "=" * 70)
    print("--- 3. Testing Guest Mode 3-Query Limit Enforcement ---")
    print("=" * 70)

    # Guest Query 1
    res_chat1 = client.post("/api/v1/chat", json={"question": "What is the stock price of RELIANCE?", "symbols": ["RELIANCE"]})
    print(f"Guest Chat 1 Status: {res_chat1.status_code} | Queries Remaining: {res_chat1.json().get('queries_remaining')}")
    assert res_chat1.status_code == 200, "Guest chat 1 failed!"

    # Guest Query 2
    res_chat2 = client.post("/api/v1/chat", json={"question": "What is the P/E ratio of TCS?", "symbols": ["TCS"]})
    print(f"Guest Chat 2 Status: {res_chat2.status_code} | Queries Remaining: {res_chat2.json().get('queries_remaining')}")
    assert res_chat2.status_code == 200, "Guest chat 2 failed!"

    # Guest Query 3
    res_chat3 = client.post("/api/v1/chat", json={"question": "What is the ROE for RELIANCE?", "symbols": ["RELIANCE"]})
    print(f"Guest Chat 3 Status: {res_chat3.status_code} | Queries Remaining: {res_chat3.json().get('queries_remaining')}")
    assert res_chat3.status_code == 200, "Guest chat 3 failed!"

    # Guest Query 4 (Should return 403 Forbidden)
    res_chat4 = client.post("/api/v1/chat", json={"question": "Compare RELIANCE and TCS", "symbols": ["RELIANCE", "TCS"]})
    print(f"Guest Chat 4 Status: {res_chat4.status_code} | Response: {res_chat4.json()}")
    assert res_chat4.status_code == 403, "4th Guest query should have been blocked with 403 Forbidden!"
    print("  [PASSED] Guest 3-query limit enforcement verified successfully.")

    print("\n" + "=" * 70)
    print("--- 4. Testing Authenticated Bearer JWT User Request ---")
    print("=" * 70)

    # Create test user in DB
    db = SessionLocal()
    user = db.query(User).filter(User.email == "test_trader@example.com").first()
    if not user:
        user = User(
            email="test_trader@example.com",
            name="Test Trader",
            provider="google",
            provider_user_id="google_test_12345",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Issue JWT token
    jwt_token = create_access_token({"user_id": user.id, "email": user.email})
    db.close()

    # Make authenticated request (with Bearer token header)
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res_auth_chat = client.post(
        "/api/v1/chat",
        json={"question": "Compare RELIANCE vs TCS on market cap and valuation ratios.", "symbols": ["RELIANCE", "TCS"]},
        headers=headers,
    )

    print(f"Auth Chat Status: {res_auth_chat.status_code}")
    print(f"Auth Queries Remaining: {res_auth_chat.json().get('queries_remaining')} (-1 = Unlimited)")
    assert res_auth_chat.status_code == 200, "Authenticated chat request failed!"
    print("  [PASSED] Authenticated Bearer JWT request verified successfully.")

    print("\n" + "=" * 70)
    print("     FASTAPI BACKEND VERIFICATION COMPLETED SUCCEEDED!  ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_backend_api()
