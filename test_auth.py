import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables before importing app modules
TEST_DB_FILE = "test_auth_price_tracker.db"
os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test_super_secret_key"

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app import models
from backend.app.services.auth import hash_password, verify_password, create_access_token, verify_token

# Configure a test database engine
engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def run_tests():
    print("Starting User Authentication & SaaS Isolation Tests...")
    
    # 1. Clean and Recreate DB schema
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
            
    Base.metadata.create_all(bind=engine)
    print("[OK] Test database initialized.")

    # 2. Test Password Hashing
    pw = "mysecretpassword123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrongpassword", hashed) is False
    print("[OK] Password hashing and verification passed.")

    # 3. Test JWT Tokens
    payload = {"sub": "test@example.com"}
    token = create_access_token(payload)
    decoded = verify_token(token)
    assert decoded is not None
    assert decoded["sub"] == "test@example.com"
    assert verify_token("invalid_token") is None
    print("[OK] JWT token generation and verification passed.")

    # 4. Test User Registration
    payload = {"name": "Alice Developer", "email": "alice@example.com", "password": "securepassword123"}
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice Developer"
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data
    print("[OK] User registration succeeds with valid data.")

    # 4b. Password too short (<8 chars)
    payload_short = {"name": "Bob", "email": "bob@example.com", "password": "123"}
    resp_short = client.post("/api/auth/register", json=payload_short)
    assert resp_short.status_code == 400
    assert "Password must be at least 8 characters long" in resp_short.json()["detail"]
    print("[OK] Short password rejected successfully.")

    # 4c. Duplicate email registration
    resp_dup = client.post("/api/auth/register", json=payload)
    assert resp_dup.status_code == 400
    assert "already exists" in resp_dup.json()["detail"]
    print("[OK] Duplicate email address registration blocked successfully.")

    # 5. Test User Login
    # 5a. Successful login
    login_data = {"username": "alice@example.com", "password": "securepassword123"}
    resp = client.post("/api/auth/login", data=login_data)
    assert resp.status_code == 200
    token_info = resp.json()
    assert "access_token" in token_info
    assert token_info["token_type"] == "bearer"
    alice_token = token_info["access_token"]
    print("[OK] Login succeeds with valid credentials.")

    # 5b. Invalid password login
    invalid_data = {"username": "alice@example.com", "password": "wrongpassword"}
    resp_invalid = client.post("/api/auth/login", data=invalid_data)
    assert resp_invalid.status_code == 401
    assert "Incorrect email or password" in resp_invalid.json()["detail"]
    print("[OK] Login fails with incorrect credentials.")

    # 6. Test Protected Routes Access
    # 6a. Try fetching products without token
    resp_unauthed = client.get("/api/products/")
    assert resp_unauthed.status_code == 401
    print("[OK] Product routes block unauthenticated requests.")

    # 6b. Try with token
    headers_alice = {"Authorization": f"Bearer {alice_token}"}
    resp_authed = client.get("/api/products/", headers=headers_alice)
    assert resp_authed.status_code == 200
    assert resp_authed.json() == []
    print("[OK] Product routes allow authenticated requests.")

    # 7. Test User-Specific Product Isolation
    # 7a. Register user Bob
    resp_bob_reg = client.post("/api/auth/register", json={
        "name": "Bob Programmer", 
        "email": "bob@example.com", 
        "password": "bobpassword123"
    })
    assert resp_bob_reg.status_code == 201
    
    # 7b. Login Bob
    bob_token = client.post("/api/auth/login", data={"username": "bob@example.com", "password": "bobpassword123"}).json()["access_token"]
    headers_bob = {"Authorization": f"Bearer {bob_token}"}

    # 7c. Alice creates Product A
    payload_a = {"name": "Alice Product", "category": "Electronics"}
    resp_create_a = client.post("/api/products/", json=payload_a, headers=headers_alice)
    assert resp_create_a.status_code == 201
    prod_a_id = resp_create_a.json()["id"]

    # 7d. Bob creates Product B
    payload_b = {"name": "Bob Product", "category": "Books"}
    resp_create_b = client.post("/api/products/", json=payload_b, headers=headers_bob)
    assert resp_create_b.status_code == 201
    prod_b_id = resp_create_b.json()["id"]

    # 7e. Verify Alice only sees Product A
    resp_list_alice = client.get("/api/products/", headers=headers_alice)
    alice_prods = resp_list_alice.json()
    assert len(alice_prods) == 1
    assert alice_prods[0]["id"] == prod_a_id
    assert alice_prods[0]["name"] == "Alice Product"

    # 7f. Verify Bob only sees Product B
    resp_list_bob = client.get("/api/products/", headers=headers_bob)
    bob_prods = resp_list_bob.json()
    assert len(bob_prods) == 1
    assert bob_prods[0]["id"] == prod_b_id
    assert bob_prods[0]["name"] == "Bob Product"
    print("[OK] User database products isolation verified successfully.")

    # 7g. Verify Alice cannot view Bob's product B (should raise 404)
    resp_get_b = client.get(f"/api/products/{prod_b_id}", headers=headers_alice)
    assert resp_get_b.status_code == 404

    # 7h. Verify Alice cannot delete Bob's product B
    resp_del_b = client.delete(f"/api/products/{prod_b_id}", headers=headers_alice)
    assert resp_del_b.status_code == 404
    print("[OK] Route access restrictions across users checked successfully.")

    # 8. Test Forgot & Reset Password
    # 8a. Trigger forgot password request
    resp_forgot = client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    assert resp_forgot.status_code == 200
    token = resp_forgot.json()["token"]
    assert token is not None

    # 8b. Reset password using valid token
    resp_reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": "newalicepassword123"})
    assert resp_reset.status_code == 200
    assert resp_reset.json()["status"] == "success"

    # 8c. Verify old password login fails
    resp_old_login = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "securepassword123"})
    assert resp_old_login.status_code == 401

    # 8d. Verify new password login succeeds
    resp_new_login = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "newalicepassword123"})
    assert resp_new_login.status_code == 200
    assert "access_token" in resp_new_login.json()
    print("[OK] Forgot and Reset password flow verified successfully.")

    # 9. Clean up test database
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
    print("[OK] Test database cleanup successfully completed.")
    print("\nALL USER AUTHENTICATION & MULTI-USER SaaS TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] Test assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error during test run: {e}")
        sys.exit(1)
