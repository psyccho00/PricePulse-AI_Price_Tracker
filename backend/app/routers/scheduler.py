from fastapi import APIRouter, Depends, HTTPException, status
from backend.app import schemas, models
from backend.app.services import scheduler
from backend.app.dependencies import get_current_user

router = APIRouter(
    prefix="/scheduler",
    tags=["scheduler"]
)

@router.get("/status", response_model=schemas.SchedulerStatusResponse)
def read_scheduler_status(current_user: models.User = Depends(get_current_user)):
    """
    Returns the running state, interval, last run, and next run details of the background scheduler.
    """
    try:
        return scheduler.get_scheduler_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read scheduler status: {str(e)}"
        )

@router.get("/cache-stats")
def get_scraper_cache_statistics(current_user: models.User = Depends(get_current_user)):
    """
    Exposes cache telemetry metrics: hits, misses, expirations, hit rate, and latency averages.
    """
    from backend.app.services.scraper import get_cache_stats
    return get_cache_stats()

@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
def trigger_scheduler_check(current_user: models.User = Depends(get_current_user)):
    """
    Triggers an immediate background check run on all registered links.
    """
    try:
        # We can run it in a background thread or trigger the job immediately
        # get_job("price_check_job").modify(next_run_time=datetime.datetime.now()) or just call job
        from backend.app.services.scheduler import scheduler as s_instance
        job = s_instance.get_job("price_check_job")
        if job:
            job.modify(next_run_time=None) # run immediately (APScheduler trigger)
            # Alternatively, we can also execute the job directly in a background thread:
            # import threading
            # threading.Thread(target=check_all_prices_job).start()
            # But modifying next_run_time is standard and clean. Let's do both to ensure it works!
            import datetime
            job.modify(next_run_time=datetime.datetime.now())
            return {"status": "success", "message": "Scheduler check job triggered successfully."}
        else:
            # If job not found, just trigger the function in background
            import threading
            from backend.app.services.scheduler import check_all_prices_job
            threading.Thread(target=check_all_prices_job, daemon=True).start()
            return {"status": "success", "message": "Scheduler check job executed in a fallback background thread."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger scheduler: {str(e)}"
        )
