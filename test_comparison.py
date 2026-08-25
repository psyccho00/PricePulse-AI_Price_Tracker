import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test database variables
os.environ["DATABASE_URL"] = "sqlite:///./test_price_tracker_comp.db"
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.main import app
from backend.app.database import Base, get_db, engine as app_engine

TEST_DATABASE_URL = "sqlite:///./test_price_tracker_comp.db"
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

# Scraper mock to isolate database tests from network calls and layout fluctuations
def dummy_scrape(url):
    if "flipkart" in url:
        return {"website": "flipkart", "title": "Flipkart Pixel", "price": None, "in_stock": True, "error": None}
    elif "amazon" in url:
        return {"website": "amazon", "title": "Amazon Pixel", "price": None, "in_stock": True, "error": None}
    elif "myntra" in url:
        return {"website": "myntra", "title": "Myntra Pixel", "price": None, "in_stock": True, "error": None}
    return {"website": "unknown", "title": "Unknown", "price": None, "in_stock": False, "error": None}

@patch("backend.app.crud.scrape_product", side_effect=dummy_scrape)
def run_tests(mock_scraper):
    print("Running cross-website comparison engine tests (with mocked scrapers)...")
    
    # 1. Recreate DB
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

    # 2. Create a Product
    response = client.post("/api/products/", json={"name": "Pixel 8 Pro", "category": "Electronics"}, headers=headers)
    assert response.status_code == 201
    product = response.json()
    product_id = product["id"]
    print(f"[OK] Product created. ID: {product_id}")

    # 3. Create three platform links with different prices
    # Flipkart deal: INR 75,000 (cheapest)
    client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.flipkart.com/pixel-8-pro",
        "website": "flipkart",
        "current_price": 75000.00
    }, headers=headers)
    
    # Amazon deal: INR 78,000
    client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.amazon.in/pixel-8-pro",
        "website": "amazon",
        "current_price": 78000.00
    }, headers=headers)
    
    # Myntra deal: INR 82,000 (most expensive)
    client.post("/api/links/", json={
        "product_id": product_id,
        "url": "https://www.myntra.com/pixel-8-pro",
        "website": "myntra",
        "current_price": 82000.00
    }, headers=headers)
    print("[OK] Tracked links created for Flipkart (INR 75k), Amazon (INR 78k), and Myntra (INR 82k).")

    # 4. Fetch and evaluate comparison metrics
    response = client.get(f"/api/products/{product_id}/comparison", headers=headers)
    assert response.status_code == 200
    comp_res = response.json()
    
    print("DEBUG: comp_res =", comp_res)
    
    assert comp_res["product_id"] == product_id
    assert comp_res["best_platform"] == "flipkart"
    assert comp_res["lowest_price"] == 75000.00
    assert comp_res["highest_price"] == 82000.00
    assert comp_res["savings_amount"] == 7000.00  # 82,000 - 75,000
    print("[OK] Best platform, lowest/highest pricing, and overall savings checks passed.")

    # Validate individual comparisons list
    comparisons = {c["platform"]: c for c in comp_res["comparisons"]}
    
    # Flipkart checks
    assert comparisons["flipkart"]["is_best_deal"] is True
    assert comparisons["flipkart"]["savings_vs_this"] == 0.0
    
    # Amazon checks
    assert comparisons["amazon"]["is_best_deal"] is False
    assert comparisons["amazon"]["savings_vs_this"] == 3000.00  # 78,000 - 75,000
    
    # Myntra checks
    assert comparisons["myntra"]["is_best_deal"] is False
    assert comparisons["myntra"]["savings_vs_this"] == 7000.00  # 82,000 - 75,000
    print("[OK] Individual platform comparison savings checks passed.")

    # 5. Clean up
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app_engine.dispose()
    if os.path.exists("./test_price_tracker_comp.db"):
        os.remove("./test_price_tracker_comp.db")
    print("[OK] Test Database file cleaned up.")
    print("\nALL PRICE COMPARISON INTEGRATION TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
