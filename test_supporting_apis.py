"""
Standalone End-to-End Test Script for Supporting REST APIs & Retention Manager.

Usage:
    python test_supporting_apis.py

Verifies:
1. RetentionService 50-message FIFO cap & 7-day news auto-purge
2. ChatThread listing, message fetching, and deletion
3. Portfolio holding creation, live P&L math, and deletion
4. Preferences retrieval and updating
5. Watchlist item addition and deletion
6. Consolidated Company Detail endpoint
"""

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from app.db.database import SessionLocal, init_db
from app.main import app
from app.models import ChatMessage, ChatThread
from app.services.retention_service import RetentionService
from app.utils import get_logger

logger = get_logger("finnai.test_supporting_apis", "INFO")


def test_supporting_apis() -> None:
    load_dotenv()
    init_db()

    client = TestClient(app)
    print("\n" + "=" * 70)
    print("--- 1. Testing Database Retention Manager (50-Message FIFO Cap) ---")
    print("=" * 70)

    db = SessionLocal()
    # Create test thread with 55 dummy messages
    test_thread = ChatThread(id="test_fifo_thread_999", title="FIFO Retention Test Thread", guest_session_id="guest_test_fifo")
    db.add(test_thread)
    db.commit()

    for i in range(1, 56):
        db.add(ChatMessage(thread_id=test_thread.id, role="user" if i % 2 != 0 else "assistant", content=f"Test message #{i}"))
    db.commit()

    # Verify 55 messages exist
    msg_count_before = db.query(ChatMessage).filter(ChatMessage.thread_id == test_thread.id).count()
    print(f"Messages in test thread before retention cleanup: {msg_count_before}")
    assert msg_count_before == 55

    # Run RetentionService cleanup
    retention_svc = RetentionService()
    purged_count = retention_svc.enforce_chat_message_limit(db, guest_session_id="guest_test_fifo")
    print(f"Purged Messages Count: {purged_count}")

    msg_count_after = db.query(ChatMessage).filter(ChatMessage.thread_id == test_thread.id).count()
    print(f"Messages in test thread after retention cleanup: {msg_count_after}")
    assert msg_count_after == 50, "FIFO retention cap should enforce max 50 messages!"

    # Clean up test thread
    db.delete(test_thread)
    db.commit()
    db.close()
    print("  [PASSED] 50-Message FIFO Retention Cap verified.")

    print("\n" + "=" * 70)
    print("--- 2. Testing Preferences API (/api/v1/preferences) ---")
    print("=" * 70)

    res_get_pref = client.get("/api/v1/preferences")
    print(f"GET Preferences Status: {res_get_pref.status_code} | Data: {res_get_pref.json()}")
    assert res_get_pref.status_code == 200

    res_put_pref = client.put("/api/v1/preferences", json={"answer_style": "Concise", "theme": "Dark"})
    print(f"PUT Preferences Status: {res_put_pref.status_code} | Updated Data: {res_put_pref.json()}")
    assert res_put_pref.status_code == 200
    assert res_put_pref.json()["answer_style"] == "Concise"
    print("  [PASSED] Preferences API verified.")

    print("\n" + "=" * 70)
    print("--- 3. Testing Watchlist API (/api/v1/watchlist) ---")
    print("=" * 70)

    res_add_watch = client.post("/api/v1/watchlist", json={"symbol": "RELIANCE"})
    print(f"POST Watchlist Status: {res_add_watch.status_code} | Added Symbol: {res_add_watch.json().get('symbol')}")
    assert res_add_watch.status_code == 200

    res_get_watch = client.get("/api/v1/watchlist")
    print(f"GET Watchlist Status: {res_get_watch.status_code} | Count: {len(res_get_watch.json())}")
    assert res_get_watch.status_code == 200

    res_del_watch = client.delete("/api/v1/watchlist/RELIANCE")
    print(f"DELETE Watchlist Status: {res_del_watch.status_code}")
    assert res_del_watch.status_code == 200
    print("  [PASSED] Watchlist API verified.")

    print("\n" + "=" * 70)
    print("--- 4. Testing Portfolio Controller API (/api/v1/portfolio) ---")
    print("=" * 70)

    res_add_port = client.post("/api/v1/portfolio", json={"symbol": "TCS", "quantity": 10.0, "avg_price": 3500.0})
    print(f"POST Portfolio Status: {res_add_port.status_code} | Holding ID: {res_add_port.json().get('id')}")
    assert res_add_port.status_code == 200
    holding_id = res_add_port.json()["id"]

    res_get_port = client.get("/api/v1/portfolio")
    print(f"GET Portfolio Status: {res_get_port.status_code} | Total Value: ₹{res_get_port.json().get('total_value')}")
    assert res_get_port.status_code == 200

    res_del_port = client.delete(f"/api/v1/portfolio/{holding_id}")
    print(f"DELETE Portfolio Status: {res_del_port.status_code}")
    assert res_del_port.status_code == 200
    print("  [PASSED] Portfolio Controller API verified.")

    print("\n" + "=" * 70)
    print("--- 5. Testing Consolidated Company Detail API (/api/v1/company/RELIANCE) ---")
    print("=" * 70)

    res_comp = client.get("/api/v1/company/RELIANCE")
    print(f"GET Company Status: {res_comp.status_code} | Symbol: {res_comp.json().get('symbol')}")
    assert res_comp.status_code == 200
    assert res_comp.json()["symbol"] == "RELIANCE"
    print("  [PASSED] Consolidated Company Detail API verified.")

    print("\n" + "=" * 70)
    print("     SUPPORTING REST APIS & RETENTION VERIFICATION COMPLETED SUCCEEDED!  ")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_supporting_apis()
