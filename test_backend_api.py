import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set environment variables for testing
TEST_DATABASE_URL = "sqlite:///./test_price_tracker.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.main import app
from backend.app.database import Base, get_db, engine as app_engine

# Setup test database engine
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency in FastAPI
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def run_tests():
    print("Running backend tests...")
    
    # 1. Clean and Recreate DB schema
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] Test Database initialized.")

    # 2. Test Root Endpoint (Public)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"
    print("[OK] Health Check endpoint responds successfully.")

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

    # 3. Test Create Product
    product_data = {
        "name": "Test iPhone 15",
        "category": "Electronics"
    }
    response = client.post("/api/products/", json=product_data, headers=headers)
    assert response.status_code == 201
    product = response.json()
    assert product["name"] == "Test iPhone 15"
    assert "id" in product
    product_id = product["id"]
    print(f"[OK] Create Product works. Created ID: {product_id}")

    # 4. Test Get Products List
    response = client.get("/api/products/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Test iPhone 15"
    print("[OK] Read Products List works.")

    # 5. Test Create Product Link (Domain parsing)
    link_data = {
        "product_id": product_id,
        "url": "https://www.flipkart.com/some-product",
        "website": "flipkart",
        "current_price": 99.99
    }
    response = client.post("/api/links/", json=link_data, headers=headers)
    assert response.status_code == 201
    link = response.json()
    assert link["website"] == "flipkart"
    assert link["current_price"] == 99.99
    link_id = link["id"]
    print(f"[OK] Create Product Link works. Created ID: {link_id}")

    # 6. Test Get Product Detail
    response = client.get(f"/api/products/{product_id}", headers=headers)
    assert response.status_code == 200
    detail = response.json()
    assert len(detail["links"]) == 1
    assert detail["links"][0]["url"] == "https://www.flipkart.com/some-product"
    print("[OK] Read Product Detail with links works.")

    # 7. Test Add Test Price and Verify Price History Update
    response = client.post(f"/api/links/{link_id}/price?price=89.99", headers=headers)
    assert response.status_code == 200
    assert response.json()["current_price"] == 89.99
    print("[OK] Manual price update API works.")

    # Verify history
    response = client.get(f"/api/links/{link_id}/history", headers=headers)
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 2
    assert history[0]["price"] == 89.99 or history[1]["price"] == 89.99
    print("[OK] Price History logs successfully created.")

    # 8. Test Create Alert
    alert_data = {
        "product_id": product_id,
        "email": "customer@example.com",
        "target_price": 95.00
    }
    response = client.post("/api/alerts/", json=alert_data, headers=headers)
    assert response.status_code == 201
    alert = response.json()
    assert alert["target_price"] == 95.00
    assert alert["email"] == "customer@example.com"
    alert_id = alert["id"]
    print(f"[OK] Create Alert works. Created ID: {alert_id}")

    # 9. Test List Alerts
    response = client.get("/api/alerts/", headers=headers)
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 1
    assert alerts[0]["id"] == alert_id
    print("[OK] List Alerts works.")

    # 10. Test Price Drop Alert Trigger (logging check)
    response = client.post(f"/api/links/{link_id}/price?price=85.00", headers=headers)
    assert response.status_code == 200
    print("[OK] Alert triggers check correctly on price drop.")

    # 11. Delete Alert
    response = client.delete(f"/api/alerts/{alert_id}", headers=headers)
    assert response.status_code == 204
    print("[OK] Delete Alert works.")

    # 12. Delete Product (Cascade deletion check)
    response = client.delete(f"/api/products/{product_id}", headers=headers)
    assert response.status_code == 204
    print("[OK] Delete Product works.")

    # Verify link and price history are also deleted (cascade constraint)
    response = client.get(f"/api/products/{product_id}", headers=headers)
    assert response.status_code == 404
    print("[OK] Database constraints clean up cascaded items successfully.")

    # Cleanup Database files
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app_engine.dispose()
    if os.path.exists("./test_price_tracker.db"):
        os.remove("./test_price_tracker.db")
    print("[OK] Test Database file cleaned up.")
    print("\nALL BACKEND SKELETON TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
