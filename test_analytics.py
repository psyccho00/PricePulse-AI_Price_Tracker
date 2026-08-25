import os
import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test_price_tracker_analytics.db"
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.main import app
from backend.app.database import Base, get_db, engine as app_engine
from backend.app import models

TEST_DATABASE_URL = "sqlite:///./test_price_tracker_analytics.db"
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

# Dummy scraper mock
def dummy_scrape(url):
    return {"website": "amazon", "title": "Mock Product", "price": None, "in_stock": True, "error": None}

@patch("backend.app.crud.scrape_product", side_effect=dummy_scrape)
def run_tests(mock_scraper):
    print("Running price history and analytics integration tests...")
    
    # 1. Clean and Recreate DB
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] Test Database initialized.")

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

    # 2. Create Product
    response = client.post("/api/products/", json={"name": "Pixel 8 Pro", "category": "Electronics"}, headers=headers)
    assert response.status_code == 201
    product = response.json()
    product_id = product["id"]
    print(f"[OK] Product created. ID: {product_id}")

    # 3. Create Amazon and Flipkart Links
    response_amz = client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.amazon.in/pixel-8-pro",
        "website": "amazon",
        "current_price": 78000.00
    }, headers=headers)
    amz_link_id = response_amz.json()["id"]

    response_fk = client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.flipkart.com/pixel-8-pro",
        "website": "flipkart",
        "current_price": 75000.00
    }, headers=headers)
    fk_link_id = response_fk.json()["id"]
    print("[OK] Product links created for Amazon and Flipkart.")

    # 4. Seed Price History directly via SQLAlchemy Session
    db = TestingSessionLocal()
    try:
        # Clear default histories created on link setup
        db.query(models.PriceHistory).delete()
        db.commit()

        base_time = datetime.datetime.utcnow() - datetime.timedelta(days=10)

        # Amazon logs
        amz_logs = [
            models.PriceHistory(product_link_id=amz_link_id, price=79000.00, scraped_at=base_time),
            models.PriceHistory(product_link_id=amz_link_id, price=78000.00, scraped_at=base_time + datetime.timedelta(days=2))
        ]
        
        # Flipkart logs
        fk_logs = [
            models.PriceHistory(product_link_id=fk_link_id, price=77000.00, scraped_at=base_time + datetime.timedelta(days=1)),
            models.PriceHistory(product_link_id=fk_link_id, price=75000.00, scraped_at=base_time + datetime.timedelta(days=3))
        ]
        
        db.add_all(amz_logs + fk_logs)
        db.commit()
        print("[OK] Custom price history timeline logs seeded (prices: 79k, 77k, 78k, 75k).")
    finally:
        db.close()

    # 5. Test History Endpoint
    response = client.get(f"/api/analytics/{product_id}/history", headers=headers)
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 4
    assert history[0]["price"] == 79000.00  # earliest
    assert history[3]["price"] == 75000.00  # latest
    print("[OK] API: GET /api/analytics/{id}/history check passed.")

    # 6. Test Summary Endpoint
    response = client.get(f"/api/analytics/{product_id}/summary", headers=headers)
    assert response.status_code == 200
    summary = response.json()
    
    assert summary["product_id"] == product_id
    assert summary["lowest_price"] == 75000.00
    assert summary["highest_price"] == 79000.00
    assert summary["average_price"] == 77250.00  # (79 + 78 + 77 + 75)/4 = 77.25k
    assert summary["total_price_changes"] == 4
    
    assert summary["by_website"]["amazon"]["lowest_price"] == 78000.00
    assert summary["by_website"]["amazon"]["highest_price"] == 79000.00
    assert summary["by_website"]["amazon"]["average_price"] == 78500.00
    assert summary["by_website"]["amazon"]["total_price_changes"] == 2
    
    assert summary["by_website"]["flipkart"]["lowest_price"] == 75000.00
    assert summary["by_website"]["flipkart"]["highest_price"] == 77000.00
    assert summary["by_website"]["flipkart"]["average_price"] == 76000.00
    assert summary["by_website"]["flipkart"]["total_price_changes"] == 2
    print("[OK] API: GET /api/analytics/{id}/summary check passed.")

    # 7. Test Target Feasibility Analysis Endpoint
    response = client.get(f"/api/analytics/{product_id}/target-analysis?target_price=78000.0", headers=headers)
    assert response.status_code == 200
    analysis = response.json()
    
    assert analysis["product_id"] == product_id
    assert analysis["target_price"] == 78000.0
    assert len(analysis["dates_below_target"]) == 3
    assert analysis["frequency"] == 0.75  # 3/4 = 75%
    assert "Buy Now" in analysis["recommendation"]
    
    response = client.get(f"/api/analytics/{product_id}/target-analysis?target_price=74000.0", headers=headers)
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["frequency"] == 0.0
    assert "never reached" in analysis["recommendation"]
    print("[OK] API: GET /api/analytics/{id}/target-analysis checks passed.")

    # 8. Clean up
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app_engine.dispose()
    if os.path.exists("./test_price_tracker_analytics.db"):
        os.remove("./test_price_tracker_analytics.db")
    print("[OK] Test Database file cleaned up.")
    print("\nALL HISTORICAL ANALYTICS AND TARGET ANALYSIS TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
