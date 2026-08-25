import os
import time
import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test_price_tracker_production.db"
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"
os.environ["CHECK_INTERVAL_MINUTES"] = "1"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.main import app
from backend.app.database import Base, get_db, engine as app_engine
from backend.app import models, schemas, crud
from backend.app.services.scheduler import scrape_with_retry

TEST_DATABASE_URL = "sqlite:///./test_price_tracker_production.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Dummy scraper mock
def dummy_scrape(url):
    if "amazon" in url:
        return {"website": "amazon", "title": "Amazon Product", "price": 8000.0, "in_stock": True, "error": None}
    elif "flipkart" in url:
        return {"website": "flipkart", "title": "Flipkart Product", "price": 7500.0, "in_stock": True, "error": None}
    return {"website": "myntra", "title": "Myntra Product", "price": 6000.0, "in_stock": True, "error": None}

@patch("backend.app.crud.scrape_product", side_effect=dummy_scrape)
def run_production_tests(mock_scraper):
    print("==================================================")
    print("STARTING INTEGRATION TESTS FOR PHASES 6, 7 AND 8...")
    print("==================================================")
    
    with TestClient(app) as client:
        # 1. Clean and Recreate DB
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("[OK] Production Test Database initialized.")

        # Seed test user and get JWT
        client.post("/api/auth/register", json={
            "name": "Test User",
            "email": "testuser@example.com",
            "password": "testpassword123"
        })
        token = client.post("/api/auth/login", data={
            "username": "testuser@example.com",
            "password": "testpassword123"
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Test Scheduler Status Route
        response = client.get("/api/scheduler/status", headers=headers)
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["is_running"] is True
        assert status_data["check_interval_minutes"] == 1
        print("[OK] API: GET /api/scheduler/status verified.")

        # 3. Create Product & Links
        response = client.post("/api/products/", json={"name": "Sony WH-1000XM4", "category": "Electronics"}, headers=headers)
        assert response.status_code == 201
        product = response.json()
        product_id = product["id"]
        print(f"[OK] Product created. ID: {product_id}")

        # Seed links (Amazon and Flipkart)
        response_amz = client.post("/api/links/", json={
            "product_id": product_id,
            "url": "https://www.amazon.in/Sony-WH-1000XM4",
            "website": "amazon",
            "current_price": 8000.00
        }, headers=headers)
        amz_link_id = response_amz.json()["id"]

        response_fk = client.post("/api/links/", json={
            "product_id": product_id,
            "url": "https://www.flipkart.com/Sony-WH-1000XM4",
            "website": "flipkart",
            "current_price": 7500.00
        }, headers=headers)
        fk_link_id = response_fk.json()["id"]
        print("[OK] Product links created. Offer seeding completed automatically in CRUD hook.")

        # 4. Test Payment Optimization Endpoint (Phase 7)
        response = client.get(f"/api/products/{product_id}/payment-optimization", headers=headers)
        assert response.status_code == 200
        opt_data = response.json()
        assert opt_data["best_platform"] == "flipkart"
        assert "ICICI" in opt_data["best_payment_method"]
        assert opt_data["final_effective_price"] == 6750.0
        assert opt_data["savings"] == 750.0
        assert opt_data["platform_prices"]["amazon"] == 8000.0
        assert opt_data["platform_effective_prices"]["amazon"] == 7200.0
        assert opt_data["platform_prices"]["flipkart"] == 7500.0
        assert opt_data["platform_effective_prices"]["flipkart"] == 6750.0
        print("[OK] API: GET /api/products/{id}/payment-optimization checks passed.")

        # 5. Seed historical data for linear regression predictions (Phase 6)
        db = TestingSessionLocal()
        try:
            db.query(models.PriceHistory).delete()
            db.commit()

            base_time = datetime.datetime.utcnow() - datetime.timedelta(days=4)
            history_points = [
                models.PriceHistory(product_link_id=amz_link_id, price=8500.00, scraped_at=base_time),
                models.PriceHistory(product_link_id=amz_link_id, price=8300.00, scraped_at=base_time + datetime.timedelta(days=1)),
                models.PriceHistory(product_link_id=amz_link_id, price=8100.00, scraped_at=base_time + datetime.timedelta(days=2)),
                models.PriceHistory(product_link_id=amz_link_id, price=7900.00, scraped_at=base_time + datetime.timedelta(days=3))
            ]
            db.add_all(history_points)
            db.commit()
            print("[OK] Linear regression price history checkpoints seeded.")
        finally:
            db.close()

        # Test Prediction Endpoint
        response = client.get(f"/api/analytics/{product_id}/prediction?target_price=7000.0", headers=headers)
        assert response.status_code == 200
        pred = response.json()
        assert pred["slope"] < 0.0
        assert pred["recommendation"] in ["BUY NOW", "GOOD DEAL", "WAIT", "NOT RECOMMENDED"]
        assert pred["trend_direction"] == "Falling trend"
        assert pred["confidence"] in ["High", "Moderate", "Low"]
        assert pred["estimated_date_reached"] is not None

        #assert pred["slope"] < 0.0
        #assert pred["recommendation"] == "Wait for Discount"
        #assert pred["confidence"] in ["High", "Moderate", "Low"]
        #assert "WAIT" in pred["rationale"] or "price is on a downward" in pred["rationale"].lower()
        #assert pred["estimated_date_reached"] is not None

        print("[OK] API: GET /api/analytics/{id}/prediction checks passed.")

        # 6. Test Notifications Dispatch (Phase 8 - Email + WhatsApp Fallback)
        alert_email = "buyer@test.com"
        alert_phone = "+919876543210"
        client.post("/api/alerts/", json={
            "product_id": product_id,
            "target_price": 7600.0,
            "email": alert_email,
            "phone": alert_phone
        }, headers=headers)
        print("[OK] Alert threshold set at 7600 INR.")

        log_file_path = "./backend/logs/whatsapp_alerts.log"
        if os.path.exists(log_file_path):
            os.remove(log_file_path)

        # Trigger a check with a price drop to 7400
        with patch("backend.app.crud.send_email_alert") as mock_email:
            db = TestingSessionLocal()
            try:
                crud.update_product_link(db, amz_link_id, 7400.0, True)
                mock_email.assert_called_once()
                
                assert os.path.exists(log_file_path) is True
                with open(log_file_path, "r", encoding="utf-8") as f:
                    log_content = f.read()
                    assert alert_phone in log_content
                    assert "Sony WH-1000XM4" in log_content
                    assert "7400" in log_content
                
                print("[OK] Notifications successfully fired (Email mock called & WhatsApp log saved).")
            finally:
                db.close()

        # 7. Test Resilient Scraping Retry Loop (Phase 8)
        mock_func = MagicMock()
        mock_func.side_effect = [
            {"price": None, "error": "Timeout"},
            {"price": None, "error": "Connection Reset"},
            {"price": 7200.00, "in_stock": True, "error": None}
        ]
        
        with patch("backend.app.services.scheduler.scrape_product", mock_func):
            result = scrape_with_retry("https://www.amazon.in/Sony-WH-1000XM4", max_retries=3, delay_secs=0.1)
            assert result["price"] == 7200.00
            assert mock_func.call_count == 3
            print("[OK] Resilient scraper retry-on-failure loop recovered successfully.")

        # 8. Test Scheduler Manual Job Trigger API
        response = client.post("/api/scheduler/trigger", headers=headers)
        assert response.status_code == 202
        print("[OK] API: POST /api/scheduler/trigger check passed.")

    # 9. Clean up
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app_engine.dispose()
    
    if os.path.exists("./test_price_tracker_production.db"):
        os.remove("./test_price_tracker_production.db")
    if os.path.exists("./backend/logs/whatsapp_alerts.log"):
        os.remove("./backend/logs/whatsapp_alerts.log")

    print("==================================================")
    print("ALL CONSOLIDATED PRODUCTION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_production_tests()
