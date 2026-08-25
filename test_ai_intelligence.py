import os
import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test_price_tracker_ai.db"
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.main import app
from backend.app.database import Base, get_db, engine as app_engine
from backend.app import models

TEST_DATABASE_URL = "sqlite:///./test_price_tracker_ai.db"
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
    return {"website": "amazon", "title": "Mock Product", "price": None, "in_stock": True, "error": None}

@patch("backend.app.crud.scrape_product", side_effect=dummy_scrape)
def run_tests(mock_scraper):
    print("Running Phase 2 AI Intelligence Upgrade Integration Tests...")
    
    # 1. Clean and Recreate DB
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] Test Database initialized.")

    # Seed test user and get JWT
    client.post("/api/auth/register", json={
        "name": "AI User",
        "email": "aiuser@example.com",
        "password": "testpassword123"
    })
    token = client.post("/api/auth/login", data={
        "username": "aiuser@example.com",
        "password": "testpassword123"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Product
    response = client.post("/api/products/", json={"name": "Sony Headphones", "category": "Electronics"}, headers=headers)
    assert response.status_code == 201
    product = response.json()
    product_id = product["id"]
    print(f"[OK] Product created. ID: {product_id}")

    # 3. Create Link
    response_link = client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.amazon.in/sony-headphones",
        "website": "amazon",
        "current_price": 20000.00
    }, headers=headers)
    link_id = response_link.json()["id"]
    print("[OK] Link created.")

    # 4. Seed custom history logs directly
    db = TestingSessionLocal()
    try:
        db.query(models.PriceHistory).delete()
        db.commit()

        base_time = datetime.datetime.utcnow() - datetime.timedelta(days=10)

        # Seed decreasing prices: 25k, 24k, 23k, 22k, 20k
        logs = [
            models.PriceHistory(product_link_id=link_id, price=25000.00, scraped_at=base_time),
            models.PriceHistory(product_link_id=link_id, price=24000.00, scraped_at=base_time + datetime.timedelta(days=2)),
            models.PriceHistory(product_link_id=link_id, price=23000.00, scraped_at=base_time + datetime.timedelta(days=4)),
            models.PriceHistory(product_link_id=link_id, price=22000.00, scraped_at=base_time + datetime.timedelta(days=6)),
            models.PriceHistory(product_link_id=link_id, price=20000.00, scraped_at=base_time + datetime.timedelta(days=8))
        ]
        db.add_all(logs)
        db.commit()
        print("[OK] Custom history seeded: 25k, 24k, 23k, 22k, 20k.")
    finally:
        db.close()

    # 5. Create an Alert with Target Price = 21,000.00 (which was met 1 time out of 5 logs: 20k is <= 21k)
    response_alert = client.post("/api/alerts/", json={
        "product_id": product_id,
        "target_price": 21000.00,
        "email": "aiuser@example.com"
    }, headers=headers)
    assert response_alert.status_code == 201
    print("[OK] Target Alert created at Rs. 21,000.00.")

    # 6. Test Prediction Endpoint
    response = client.get(f"/api/analytics/{product_id}/prediction?target_price=21000.0", headers=headers)
    assert response.status_code == 200
    prediction = response.json()

    # Check key predictions values are present and correct
    assert "ai_buy_score" in prediction
    assert "star_rating" in prediction
    assert "buy_score_reasons" in prediction
    assert "predicted_price_tomorrow" in prediction
    assert "predicted_price_next_week" in prediction
    assert "prediction_confidence_pct" in prediction
    assert "smart_recommendation" in prediction
    assert "smart_recommendation_reason" in prediction
    assert "target_probability_pct" in prediction
    assert "trend_direction" in prediction
    
    # 20k is <= 21k (so 1 of the 5 logs met the target => 20% success rate historically, but target probability is 100% since current price is below target)
    assert prediction["target_probability_pct"] == 100.0
    assert prediction["historical_success_rate_pct"] == 20.0
    assert "Falling trend" in prediction["trend_direction"]
    print("[OK] /api/analytics/{id}/prediction fields validated.")

    # 7. Test Portfolio AI Summary Endpoint
    response_sum = client.get("/api/analytics/portfolio-ai-summary", headers=headers)
    assert response_sum.status_code == 200
    summary = response_sum.json()

    assert summary["portfolio_ai_score"] > 0
    assert summary["average_buy_score"] > 0
    assert summary["best_product_to_buy"]["product_id"] == product_id
    assert summary["best_product_to_buy"]["ai_buy_score"] == prediction["ai_buy_score"]
    print("[OK] /api/analytics/portfolio-ai-summary fields validated.")

    # 8. Clean up
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app_engine.dispose()
    if os.path.exists("./test_price_tracker_ai.db"):
        os.remove("./test_price_tracker_ai.db")
    print("[OK] Test Database file cleaned up.")
    print("\nALL PHASE 2 AI INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
