import os
import sys
import time
import datetime
import psutil
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables
TEST_DB_FILE = "stress_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "stress_test_secret_key"
os.environ["SMTP_ADDRESS"] = "smtp.test.com"
os.environ["EMAIL_ADDRESS"] = "test@test.com"
os.environ["EMAIL_PASSWORD"] = "password"

from backend.app.main import app
from backend.app.database import Base, get_db
from backend.app import models

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

# Helper to track CPU & memory usage
def get_resource_usage():
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    cpu_pct = process.cpu_percent(interval=0.1)
    return mem_mb, cpu_pct

def seed_database(product_count: int, history_count: int):
    """
    Cleans database and seeds product_count products and history_count history logs.
    """
    print(f"\n[Seed] Initializing DB with {product_count} products and {history_count} history records...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        # Create test user
        user = models.User(
            name="Stress Test User",
            email="stress@example.com",
            hashed_password="hashed_stress_password"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create products & links
        products = []
        links = []
        
        websites = ["amazon", "flipkart", "myntra"]
        
        for i in range(1, product_count + 1):
            prod = models.Product(
                name=f"Stress Product {i}",
                category="Gadgets",
                user_id=user.id
            )
            products.append(prod)
            
        db.add_all(products)
        db.commit()
        
        # Add links for products
        for i, prod in enumerate(products):
            # Alternate websites
            site = websites[i % len(websites)]
            link = models.ProductLink(
                product_id=prod.id,
                url=f"https://www.{site}.com/product-{prod.id}",
                website=site,
                current_price=1000.0 + (i * 10)
            )
            links.append(link)
            
        db.add_all(links)
        db.commit()
        
        # Create alerts
        alerts = []
        for prod in products:
            alert = models.Alert(
                product_id=prod.id,
                email="alert@example.com",
                target_price=900.0
            )
            alerts.append(alert)
        db.add_all(alerts)
        db.commit()
        
        # Add history logs across links
        histories = []
        base_time = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        
        for i in range(history_count):
            link_index = i % len(links)
            target_link = links[link_index]
            
            # Simulated history check point
            hist = models.PriceHistory(
                product_link_id=target_link.id,
                price=target_link.current_price - (i % 50),
                scraped_at=base_time + datetime.timedelta(hours=i)
            )
            histories.append(hist)
            
        db.add_all(histories)
        db.commit()
        
        print(f"[Seed] Successfully seeded User, {len(products)} products, {len(links)} links, {len(alerts)} alerts, and {len(histories)} price histories.")
        
    finally:
        db.close()

def run_performance_benchmarks(product_count: int) -> dict:
    """
    Runs benchmark requests against FastAPI endpoints and returns results.
    """
    print(f"\n[Benchmark] Running performance benchmarks for {product_count} products scale...")
    
    # 1. Login to get token
    resp_reg = client.post("/api/auth/register", json={
        "name": "Alice Stresser",
        "email": "alice_stress@example.com",
        "password": "stresstestpassword123"
    })
    
    login_data = {"username": "alice_stress@example.com", "password": "stresstestpassword123"}
    resp_login = client.post("/api/auth/login", data=login_data)
    assert resp_login.status_code == 200, f"Login failed: {resp_login.text}"
    token = resp_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check current scale products (we should assign Alice as the owner of these products to test authed requests)
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "alice_stress@example.com").first()
        db.query(models.Product).update({models.Product.user_id: user.id})
        db.commit()
    finally:
        db.close()
        
    # Measure List Products API
    times_list = []
    for _ in range(10):
        start = time.time()
        res = client.get("/api/products/", headers=headers)
        assert res.status_code == 200
        times_list.append(time.time() - start)
        
    avg_list = sum(times_list) / len(times_list)
    p95_list = sorted(times_list)[int(len(times_list) * 0.95)]
    fastest_list = min(times_list)
    slowest_list = max(times_list)
    
    # Measure Single Product Detail API (ID: 1)
    times_detail = []
    for _ in range(10):
        start = time.time()
        res = client.get("/api/products/1", headers=headers)
        assert res.status_code in [200, 404]
        times_detail.append(time.time() - start)
        
    avg_detail = sum(times_detail) / len(times_detail)
    p95_detail = sorted(times_detail)[int(len(times_detail) * 0.95)]
    
    # Measure Product Comparison API (ID: 1)
    times_comp = []
    for _ in range(10):
        start = time.time()
        res = client.get("/api/products/1/comparison", headers=headers)
        assert res.status_code in [200, 404]
        times_comp.append(time.time() - start)
    avg_comp = sum(times_comp) / len(times_comp)
    
    # Measure Product Prediction API (ID: 1)
    times_pred = []
    for _ in range(10):
        start = time.time()
        res = client.get("/api/analytics/1/prediction?target_price=800.0", headers=headers)
        assert res.status_code in [200, 404]
        times_pred.append(time.time() - start)
    avg_pred = sum(times_pred) / len(times_pred)

    # Measure Scheduler Status API
    times_sched = []
    for _ in range(10):
        start = time.time()
        res = client.get("/api/scheduler/status", headers=headers)
        assert res.status_code == 200
        times_sched.append(time.time() - start)
    avg_sched = sum(times_sched) / len(times_sched)
    
    # Track resource footprint
    mem, cpu = get_resource_usage()
    
    # Measure background scheduler update run (mocked scraper)
    # Let's run check_all_prices_job directly
    from backend.app.services.scheduler import check_all_prices_job
    
    start_sched_run = time.time()
    # We temporarily patch scrape_with_retry in scheduler to prevent actual network calls during stress run
    from unittest.mock import patch
    with patch("backend.app.services.scheduler.scrape_with_retry") as mock_scrape:
        mock_scrape.return_value = {"price": 950.00, "in_stock": True, "title": "Mock Product", "image_url": None, "error": None}
        check_all_prices_job()
    scheduler_runtime = time.time() - start_sched_run
    
    print(f"[Benchmark] Complete. Avg List: {avg_list:.4f}s, Avg Detail: {avg_detail:.4f}s, Memory: {mem:.2f} MB, CPU: {cpu:.1f}%, Sched Run: {scheduler_runtime:.4f}s")
    
    return {
        "avg_list": avg_list,
        "p95_list": p95_list,
        "fastest_list": fastest_list,
        "slowest_list": slowest_list,
        "avg_detail": avg_detail,
        "p95_detail": p95_detail,
        "avg_comp": avg_comp,
        "avg_pred": avg_pred,
        "avg_sched": avg_sched,
        "scheduler_runtime": scheduler_runtime,
        "memory_mb": mem,
        "cpu_pct": cpu
    }

def cleanup():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

def main():
    try:
        # Scale 1: 100 products, 1000 histories
        seed_database(100, 1000)
        scale_100_results = run_performance_benchmarks(100)
        
        # Scale 2: 500 products, 1000 histories
        seed_database(500, 1000)
        scale_500_results = run_performance_benchmarks(500)
        
        # Print Summary Results
        print("\n" + "="*50)
        print("STRESS TEST PERFORMANCE BENCHMARK SUMMARY")
        print("="*50)
        print(f"{'Metric':<30} | {'100 Products Scale':<18} | {'500 Products Scale':<18}")
        print("-"*74)
        print(f"{'List Products API (avg)':<30} | {scale_100_results['avg_list']:.4f} sec | {scale_500_results['avg_list']:.4f} sec")
        print(f"{'List Products API (95th)':<30} | {scale_100_results['p95_list']:.4f} sec | {scale_500_results['p95_list']:.4f} sec")
        print(f"{'Get Product Detail (avg)':<30} | {scale_100_results['avg_detail']:.4f} sec | {scale_500_results['avg_detail']:.4f} sec")
        print(f"{'Get Price Comparison (avg)':<30} | {scale_100_results['avg_comp']:.4f} sec | {scale_500_results['avg_comp']:.4f} sec")
        print(f"{'Get Price Prediction (avg)':<30} | {scale_100_results['avg_pred']:.4f} sec | {scale_500_results['avg_pred']:.4f} sec")
        print(f"{'Scheduler Status API (avg)':<30} | {scale_100_results['avg_sched']:.4f} sec | {scale_500_results['avg_sched']:.4f} sec")
        print(f"{'Background Scheduler Run':<30} | {scale_100_results['scheduler_runtime']:.4f} sec | {scale_500_results['scheduler_runtime']:.4f} sec")
        print(f"{'Process Memory Usage':<30} | {scale_100_results['memory_mb']:.2f} MB | {scale_500_results['memory_mb']:.2f} MB")
        print(f"{'Process CPU Load':<30} | {scale_100_results['cpu_pct']:.1f}% | {scale_500_results['cpu_pct']:.1f}%")
        print("="*50)
        
    finally:
        cleanup()

if __name__ == "__main__":
    main()
