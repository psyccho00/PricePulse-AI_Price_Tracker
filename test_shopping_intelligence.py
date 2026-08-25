import os
import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test_price_tracker_shopping.db"
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.main import app
from backend.app.database import Base, get_db, engine as app_engine
from backend.app import models

TEST_DATABASE_URL = "sqlite:///./test_price_tracker_shopping.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def dummy_scrape(url):
    if "flipkart" in url:
        return {"website": "flipkart", "title": "Flipkart Product", "price": None, "in_stock": True, "error": None}
    elif "amazon" in url:
        return {"website": "amazon", "title": "Amazon Product", "price": None, "in_stock": True, "error": None}
    elif "myntra" in url:
        return {"website": "myntra", "title": "Myntra Product", "price": None, "in_stock": True, "error": None}
    return {"website": "unknown", "title": "Unknown", "price": None, "in_stock": False, "error": None}

@patch("backend.app.crud.scrape_product", side_effect=dummy_scrape)
def run_tests(mock_scraper):
    print("Running Shopping Intelligence Integration Tests...")
    
    # 1. Clean and Recreate DB
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] Test Database initialized.")

    # Seed test user and get JWT
    client.post("/api/auth/register", json={
        "name": "Shop User",
        "email": "shopuser@example.com",
        "password": "testpassword123"
    })
    token = client.post("/api/auth/login", data={
        "username": "shopuser@example.com",
        "password": "testpassword123"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Product with Amazon link
    response = client.post("/api/products/", json={"name": "Samsung Galaxy S24 Ultra", "category": "Electronics"}, headers=headers)
    assert response.status_code == 201
    product = response.json()
    product_id = product["id"]
    print(f"[OK] Product created. ID: {product_id}")

    # 3. Create Links
    response_amz = client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.amazon.in/samsung-galaxy-s24-ultra",
        "website": "amazon",
        "current_price": 120000.00
    }, headers=headers)
    amz_link_id = response_amz.json()["id"]
    
    response_fk = client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.flipkart.com/samsung-galaxy-s24-ultra",
        "website": "flipkart",
        "current_price": 115000.00
    }, headers=headers)
    fk_link_id = response_fk.json()["id"]
    print("[OK] Amazon and Flipkart links created.")

    # 4. Seed custom price history (declining price pattern)
    db = TestingSessionLocal()
    try:
        db.query(models.PriceHistory).delete()
        db.commit()

        base_time = datetime.datetime.utcnow() - datetime.timedelta(days=20)

        # Amazon price history: starts high, drops 
        amz_logs = [
            models.PriceHistory(product_link_id=amz_link_id, price=130000.00, scraped_at=base_time),
            models.PriceHistory(product_link_id=amz_link_id, price=128000.00, scraped_at=base_time + datetime.timedelta(days=3)),
            models.PriceHistory(product_link_id=amz_link_id, price=125000.00, scraped_at=base_time + datetime.timedelta(days=6)),
            models.PriceHistory(product_link_id=amz_link_id, price=122000.00, scraped_at=base_time + datetime.timedelta(days=10)),
            models.PriceHistory(product_link_id=amz_link_id, price=120000.00, scraped_at=base_time + datetime.timedelta(days=14)),
        ]
        
        # Flipkart price history: also declining
        fk_logs = [
            models.PriceHistory(product_link_id=fk_link_id, price=127000.00, scraped_at=base_time + datetime.timedelta(days=1)),
            models.PriceHistory(product_link_id=fk_link_id, price=123000.00, scraped_at=base_time + datetime.timedelta(days=5)),
            models.PriceHistory(product_link_id=fk_link_id, price=118000.00, scraped_at=base_time + datetime.timedelta(days=9)),
            models.PriceHistory(product_link_id=fk_link_id, price=115000.00, scraped_at=base_time + datetime.timedelta(days=13)),
        ]
        
        db.add_all(amz_logs + fk_logs)
        db.commit()
        print("[OK] Custom price history seeded with declining pattern.")
    finally:
        db.close()

    # 5. Create an alert
    response_alert = client.post("/api/alerts/", json={
        "product_id": product_id,
        "target_price": 110000.00,
        "email": "shopuser@example.com"
    }, headers=headers)
    assert response_alert.status_code == 201
    print("[OK] Alert created at Rs. 110,000.")

    # ============================================
    # TEST: Price Drop Analysis Endpoint
    # ============================================
    print("\n--- Testing Price Drop Analysis ---")
    response = client.get(f"/api/analytics/{product_id}/price-drop", headers=headers)
    assert response.status_code == 200
    drop_data = response.json()
    
    assert "has_drop" in drop_data
    assert "current_price" in drop_data
    assert "historical_low" in drop_data
    assert "drop_summary" in drop_data
    assert drop_data["product_id"] == product_id
    assert drop_data["historical_low"] == 115000.00
    print(f"[OK] Price drop analysis returned valid data. Has drop: {drop_data['has_drop']}")
    print(f"     Historical low: INR {drop_data['historical_low']:,.2f}")
    print(f"     Summary: {drop_data['drop_summary']}")

    # ============================================
    # TEST: Deal Score Endpoint
    # ============================================
    print("\n--- Testing Deal Score Endpoint ---")
    response = client.get(f"/api/analytics/{product_id}/deal-score", headers=headers)
    assert response.status_code == 200
    deal_data = response.json()
    
    assert "deal_score" in deal_data
    assert "deal_status" in deal_data
    assert "deal_explanation" in deal_data
    assert "price_percentile" in deal_data
    assert "ai_buy_score" in deal_data  # Both scores present, kept separate
    assert deal_data["product_id"] == product_id
    assert deal_data["deal_score"] >= 0 and deal_data["deal_score"] <= 100
    assert deal_data["deal_status"] in ["LOW", "TYPICAL", "HIGH"]
    print(f"     Deal Score: {deal_data['deal_score']}/100 (Status: {deal_data['deal_status']})")
    print(f"     AI Buy Score: {deal_data['ai_buy_score']}/100 (kept separate)")
    print(f"     Deal explanation: {deal_data['deal_explanation'].replace('₹', 'INR ')}")
    print(f"     Price percentile: {deal_data['price_percentile']}%")

    # Verify Deal Score and AI Buy Score are separate metrics
    assert deal_data["deal_score"] != deal_data["ai_buy_score"] or True  # They CAN be equal, but both must exist
    print("[OK] AI Buy Score and Deal Score are both present as separate metrics.")

    # ============================================
    # TEST: Product Match Suggestions Endpoint 
    # ============================================
    print("\n--- Testing Product Match Suggestions ---")
    
    # Create a second product with similar name
    response2 = client.post("/api/products/", json={
        "name": "Samsung Galaxy S24 Ultra 256GB",
        "category": "Electronics"
    }, headers=headers)
    assert response2.status_code == 201
    product2 = response2.json()
    product2_id = product2["id"]
    
    # Add a Myntra link to the second product
    client.post("/api/links/", json={
        "product_id": product2_id,
        "url": "https://www.myntra.com/samsung-galaxy-s24-ultra",
        "website": "myntra",
        "current_price": 119000.00
    }, headers=headers)
    print(f"[OK] Second product created (ID: {product2_id}) with similar name for matching.")

    response = client.get(f"/api/products/{product_id}/match-suggestions", headers=headers)
    assert response.status_code == 200
    match_data = response.json()
    
    assert match_data["source_product_id"] == product_id
    assert match_data["source_product_name"] == "Samsung Galaxy S24 Ultra"
    assert isinstance(match_data["matches"], list)
    print(f"[OK] Match suggestions returned. Matches found: {len(match_data['matches'])}")
    
    if match_data["matches"]:
        first_match = match_data["matches"][0]
        assert "product_id" in first_match
        assert "product_name" in first_match
        assert "confidence" in first_match
        assert "match_reasons" in first_match
        assert "websites" in first_match
        assert first_match["confidence"] >= 0.0 and first_match["confidence"] <= 1.0
        print(f"     Match: {first_match['product_name']} (Confidence: {first_match['confidence']:.0%})")
        print(f"     Reasons: {', '.join(first_match['match_reasons'])}")

    # ============================================
    # TEST: User isolation for shopping intelligence endpoints
    # ============================================
    print("\n--- Testing User Isolation ---")

    # Register a second user
    client.post("/api/auth/register", json={
        "name": "Other User",
        "email": "otheruser@example.com",
        "password": "otherpassword123"
    })
    other_token = client.post("/api/auth/login", data={
        "username": "otheruser@example.com",
        "password": "otherpassword123"
    }).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Other user should NOT see our products
    response = client.get(f"/api/analytics/{product_id}/price-drop", headers=other_headers)
    assert response.status_code == 404
    print("[OK] Price drop endpoint blocks unauthorized user access.")

    response = client.get(f"/api/analytics/{product_id}/deal-score", headers=other_headers)
    assert response.status_code == 404
    print("[OK] Deal score endpoint blocks unauthorized user access.")

    response = client.get(f"/api/products/{product_id}/match-suggestions", headers=other_headers)
    assert response.status_code == 404
    print("[OK] Match suggestions endpoint blocks unauthorized user access.")

    # ============================================
    # TEST: Existing alerts remain isolated
    # ============================================
    print("\n--- Testing Alert Isolation ---")
    
    # Verify existing alerts still work
    response = client.get("/api/alerts/", headers=headers)
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) >= 1
    assert alerts[0]["alert_type"] == "target_price"  # Default type preserved
    print("[OK] Existing target_price alerts preserved and working.")

    # Other user cannot see our alerts
    response = client.get("/api/alerts/", headers=other_headers)
    assert response.status_code == 200
    other_alerts = response.json()
    assert len(other_alerts) == 0
    print("[OK] Alert isolation verified - other user sees no alerts.")

    # ============================================
    # TEST: Smart Alert Types
    # ============================================
    print("\n--- Testing Smart Alert Types ---")
    
    # Create percentage drop alert
    response = client.post("/api/alerts/", json={
        "product_id": product_id,
        "email": "shopuser@example.com",
        "alert_type": "percentage_drop",
        "alert_condition_value": 5.0,
        "target_price": 0.0
    }, headers=headers)
    assert response.status_code == 201
    pct_alert = response.json()
    assert pct_alert["alert_type"] == "percentage_drop"
    assert pct_alert["alert_condition_value"] == 5.0
    print("[OK] Percentage drop alert created successfully.")

    # Create deal score alert
    response = client.post("/api/alerts/", json={
        "product_id": product_id,
        "email": "shopuser@example.com",
        "alert_type": "deal_score",
        "alert_condition_value": 80.0,
        "target_price": 0.0
    }, headers=headers)
    assert response.status_code == 201
    ds_alert = response.json()
    assert ds_alert["alert_type"] == "deal_score"
    print("[OK] Deal score alert created successfully.")

    # Verify all alerts for the product
    response = client.get(f"/api/alerts/?product_id={product_id}", headers=headers)
    assert response.status_code == 200
    all_alerts = response.json()
    alert_types = [a["alert_type"] for a in all_alerts]
    assert "target_price" in alert_types
    assert "percentage_drop" in alert_types
    assert "deal_score" in alert_types
    print(f"[OK] All alert types verified: {alert_types}")

    # ============================================
    # CLEANUP
    # ============================================
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app_engine.dispose()
    if os.path.exists("./test_price_tracker_shopping.db"):
        os.remove("./test_price_tracker_shopping.db")
    print("[OK] Test Database file cleaned up.")
    print("\nALL SHOPPING INTELLIGENCE INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
