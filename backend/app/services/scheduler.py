import os
import time
import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

# Import database, crud, and scrapers
from backend.app.database import SessionLocal, engine
from backend.app import crud, models
from backend.app.services.scraper import scrape_product

logger = logging.getLogger("scheduler_daemon")

# Global instances
scheduler = BackgroundScheduler()
LAST_RUN_TIME = None
IS_UPDATING = False
CHECK_INTERVAL_MINS = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
MAX_SCRAPER_WORKERS = int(os.environ.get("MAX_SCRAPER_WORKERS", "8"))

def scrape_with_retry(url: str, max_retries: int = 3, delay_secs: float = 5.0, bypass_cache: bool = False) -> dict:
    """
    Scrapes a product URL, retrying automatically on parsing/timeout/connection failures.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Scraping URL (Attempt %d/%d): %s", attempt, max_retries, url)
            result = scrape_product(url, bypass_cache=bypass_cache)
            
            # If we retrieved a price, return immediately
            if result.get("price") is not None:
                logger.info("Successfully scraped price: %s", result["price"])
                return result
                
            err = result.get("error") or "Unknown price parsing error"
            logger.warning("Scrape attempt %d failed: %s", attempt, err)
            
        except Exception as e:
            logger.warning("Scrape exception on attempt %d: %s", attempt, e)
            
        if attempt < max_retries:
            time.sleep(delay_secs)
            
    # If all attempts fail, return final error dictionary
    logger.error("Scraper failed permanently for URL after %d retries: %s", max_retries, url)
    return {
        "price": None,
        "in_stock": False,
        "title": "Failed Scrape",
        "image_url": None,
        "error": "Failed after max retries."
    }

def check_all_prices_job():
    """
    APScheduler interval job. Queries all active links, scrapes them with retry concurrently, 
    and updates values in the SQLite database.
    """
    global LAST_RUN_TIME, IS_UPDATING
    LAST_RUN_TIME = datetime.datetime.utcnow()
    IS_UPDATING = True
    logger.info("Starting background scheduled check job for all product links...")
    
    start_time = time.time()
    db: Session = SessionLocal()
    try:
        # Fetch active product links
        active_links = db.query(models.ProductLink).filter(models.ProductLink.is_active == True).all()
        logger.info("Found %d active links to verify.", len(active_links))
        
        # Parallel scraping using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor
        
        # Scheduler execution always bypasses the cache
        def scrape_task(link_item):
            logger.info("Starting parallel scrape task for Link ID %d: %s", link_item.id, link_item.url)
            res = scrape_with_retry(link_item.url, bypass_cache=True)
            return (link_item.id, res)
            
        with ThreadPoolExecutor(max_workers=MAX_SCRAPER_WORKERS) as executor:
            # Map thread execution
            results = list(executor.map(scrape_task, active_links))
            
        # Write results sequentially to DB to avoid concurrency/write locks on SQLite
        for link_id, result in results:
            price = result.get("price")
            in_stock = result.get("in_stock", True)
            image_url = result.get("image_url")
            
            if price is not None:
                crud.update_product_link(
                    db=db, 
                    link_id=link_id, 
                    current_price=price, 
                    in_stock=in_stock,
                    image_url=image_url,
                    commit=False
                )
                logger.info("Successfully staged link ID %d with price: %s", link_id, price)
            else:
                logger.error("Skipping update for link ID %d: scraper returned empty price.", link_id)
                
        # Commit all staged updates in a single transaction
        db.commit()
        logger.info("Committed all batch check updates successfully.")
                
    except Exception as e:
        logger.error("Error occurred in check_all_prices_job loop: %s", e)
    finally:
        IS_UPDATING = False
        db.close()
    
    duration = time.time() - start_time
    logger.info(f"SCHEDULER_JOB_DURATION: {duration:.4f}s")
    logger.info("Background price checking job completed successfully.")

def start_scheduler():
    """
    Starts the BackgroundScheduler intervals.
    """
    global CHECK_INTERVAL_MINS
    if not scheduler.running:
        logger.info("Starting background scheduler...")
        scheduler.start()
        
        # Add the interval job
        scheduler.add_job(
            func=check_all_prices_job,
            trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINS),
            id="price_check_job",
            name="Periodic check of all active tracked prices",
            replace_existing=True
        )
        logger.info("Job added: 'price_check_job' configured to run every %d minutes.", CHECK_INTERVAL_MINS)

def stop_scheduler():
    """
    Stops the BackgroundScheduler.
    """
    if scheduler.running:
        logger.info("Stopping background scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler shutdown successfully.")

def get_scheduler_status() -> dict:
    """
    Retrieves execution logs and next scheduled check times.
    """
    is_running = scheduler.running
    next_run = None
    
    if is_running:
        job = scheduler.get_job("price_check_job")
        if job:
            next_run = job.next_run_time
            
    return {
        "is_running": is_running,
        "check_interval_minutes": CHECK_INTERVAL_MINS,
        "last_run": LAST_RUN_TIME,
        "next_run": next_run,
        "active_jobs": len(scheduler.get_jobs()) if is_running else 0,
        "is_updating": IS_UPDATING
    }
