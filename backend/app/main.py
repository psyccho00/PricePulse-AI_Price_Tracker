from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.database import engine, Base
from backend.app.routers import products, links, alerts, analytics, scheduler
from backend.app.routers.auth import router as auth_router

# Setup centralized logging
from backend.app.config_logging import setup_logging
setup_logging()

# Import scheduler lifecycle hooks
from backend.app.services.scheduler import start_scheduler, stop_scheduler

# Import and run automatic database migrations
from backend.app.migrations import run_migrations
run_migrations()

# Automatically create all SQLite tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Amazon/Multi-Website Price Tracker API",
    description="Backend service for tracking product prices across Amazon, Flipkart, and Myntra",
    version="1.0.0"
)

import time
import logging

api_logger = logging.getLogger("api_performance")

@app.middleware("http")
async def log_api_performance(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    api_logger.info(
        f"API_PERFORMANCE: {request.method} {request.url.path} "
        f"Status: {response.status_code} Duration: {duration:.4f}s"
    )
    return response

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup & Shutdown lifecycle handlers
@app.on_event("startup")
def startup_event():
    start_scheduler()

@app.on_event("shutdown")
def shutdown_event():
    stop_scheduler()

# Root endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to the Amazon/Multi-Website Price Tracker API. Go to /docs for Swagger UI documentation."
    }

# Register routers under prefix '/api'
app.include_router(auth_router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(links.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(scheduler.router, prefix="/api")
