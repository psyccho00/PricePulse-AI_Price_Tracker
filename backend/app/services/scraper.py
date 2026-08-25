import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional, Dict, Any, Tuple
import time
import os
import threading
import json
import re
import ast

def clean_scraped_title(title: Any) -> str:
    if not title:
        return "Tracked Product"
    
    if isinstance(title, dict):
        for key in ["name", "title", "productName", "brand", "text"]:
            if key in title and isinstance(title[key], str):
                return title[key].strip()
        return str(title)
    if isinstance(title, list):
        if len(title) > 0:
            return clean_scraped_title(title[0])
        return "Tracked Product"
        
    title_str = str(title).strip()
    
    if title_str.startswith("{") or title_str.startswith("["):
        try:
            parsed = json.loads(title_str)
            return clean_scraped_title(parsed)
        except Exception:
            try:
                parsed = ast.literal_eval(title_str)
                return clean_scraped_title(parsed)
            except Exception:
                pass
                
    title_str = re.sub(r"<[^>]+>", "", title_str)
    
    if "{" in title_str and "}" in title_str:
        match = re.search(r"['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]", title_str)
        if match:
            return match.group(1).strip()
        match = re.search(r"['\"]title['\"]\s*:\s*['\"]([^'\"]+)['\"]", title_str)
        if match:
            return match.group(1).strip()
            
    title_str = title_str.replace("  ", " ").strip()
    return title_str or "Tracked Product"

def clean_scraped_image_url(url: Any) -> Optional[str]:
    if not url:
        return None
        
    if isinstance(url, dict):
        for key in ["url", "src", "image", "imageUrl", "original"]:
            if key in url and isinstance(url[key], str):
                return clean_scraped_image_url(url[key])
        return None
    if isinstance(url, list):
        if len(url) > 0:
            return clean_scraped_image_url(url[0])
        return None
        
    url_str = str(url).strip()
    
    if url_str.startswith("{") or url_str.startswith("["):
        try:
            parsed = json.loads(url_str)
            return clean_scraped_image_url(parsed)
        except Exception:
            try:
                parsed = ast.literal_eval(url_str)
                return clean_scraped_image_url(parsed)
            except Exception:
                pass
                
    url_str = re.sub(r"<[^>]+>", "", url_str)
    
    if "{" in url_str or "http" not in url_str:
        match = re.search(r"(https?://[^\s'\"}]+\.(?:jpg|jpeg|png|gif|webp|svg))", url_str, re.IGNORECASE)
        if match:
            url_str = match.group(1)
        else:
            return None
            
    url_str = url_str.strip("'\"[]() ")
    
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        return None
        
    return url_str

# Import sub-scrapers
from backend.app.services.scrapers.amazon import scrape_amazon
from backend.app.services.scrapers.flipkart import scrape_flipkart
from backend.app.services.scrapers.myntra import scrape_myntra

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Dnt": "1",
    "Priority": "u=0, i",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Sec-Gpc": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 OPR/118.0.0.0",
}

# Configurable Cache TTL (default 10 minutes)
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "600"))

# Thread-safe lock for cache access
_cache_lock = threading.Lock()
# Cache storage: key -> (timestamp, data_dict)
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# Telemetry stats
_hits = 0
_misses = 0
_expirations = 0
_total_hit_time = 0.0
_total_miss_time = 0.0

# Singleton Session client for connection pooling
_session = None
_session_lock = threading.Lock()

def get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = requests.Session()
                _session.headers.update(DEFAULT_HEADERS)
    return _session

def get_cache_stats() -> Dict[str, Any]:
    with _cache_lock:
        total = _hits + _misses
        hit_rate = (_hits / total * 100) if total > 0 else 0.0
        avg_hit_time = (_total_hit_time / _hits) if _hits > 0 else 0.0
        avg_miss_time = (_total_miss_time / _misses) if _misses > 0 else 0.0
        return {
            "hits": _hits,
            "misses": _misses,
            "expirations": _expirations,
            "hit_rate_pct": round(hit_rate, 2),
            "avg_hit_time_s": round(avg_hit_time, 4),
            "avg_miss_time_s": round(avg_miss_time, 4),
            "cache_size": len(_cache)
        }

def _clean_expired_entries():
    global _expirations
    now = time.time()
    expired = [k for k, (ts, _) in _cache.items() if now - ts > CACHE_TTL_SECONDS]
    for k in expired:
        del _cache[k]
        _expirations += 1

def detect_website(url: str) -> str:
    """
    Detect the website from the URL domain.
    """
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if "amazon" in domain:
            return "amazon"
        elif "flipkart" in domain:
            return "flipkart"
        elif "myntra" in domain:
            return "myntra"
        return "unknown"
    except Exception:
        return "unknown"

def scrape_product(url: str, bypass_cache: bool = False) -> dict:
    """
    Scrapes a product URL, detecting the website, fetching HTML, 
    routing to the appropriate scraper, and returning a unified schema.
    """
    global _hits, _total_hit_time, _misses, _total_miss_time
    website = detect_website(url)
    if website == "unknown":
        return {
            "website": "unknown",
            "title": "Unknown Product",
            "price": None,
            "in_stock": False,
            "error": "Unsupported website domain. Only Amazon, Flipkart, and Myntra are supported."
        }

    key = f"{website}:{url}"

    # 1. Cache Check
    if not bypass_cache:
        start_hit_check = time.time()
        with _cache_lock:
            _clean_expired_entries()
            if key in _cache:
                _hits += 1
                _total_hit_time += (time.time() - start_hit_check)
                return _cache[key][1]

    # 2. Cache Miss / Fresh Fetch
    start_miss_time = time.time()
    try:
        session = get_session()
        # Measure scraping duration
        scrape_start = time.time()
        response = session.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Route to correct parser based on website
        if website == "amazon":
            price, title, in_stock, image_url = scrape_amazon(soup)
        elif website == "flipkart":
            price, title, in_stock, image_url = scrape_flipkart(soup)
        elif website == "myntra":
            price, title, in_stock, image_url = scrape_myntra(soup)
        else:
            price, title, in_stock, image_url = None, None, False, None

        title_fallback = {
            "amazon": "Amazon Product",
            "flipkart": "Flipkart Product",
            "myntra": "Myntra Product"
        }.get(website, "Tracked Product")

        scrape_duration = time.time() - scrape_start
        # Structured log for scraping duration
        import logging
        logging.getLogger("scraper_performance").info(
            f"SCRAPE_DURATION: {scrape_duration:.4f}s Website: {website} URL: {url}"
        )

        result = {
            "website": website,
            "title": clean_scraped_title(title or title_fallback),
            "price": price,
            "in_stock": in_stock,
            "image_url": clean_scraped_image_url(image_url),
            "error": None if price is not None else "Price not found on page layout."
        }

        # Cache valid successful scrape
        if price is not None:
            with _cache_lock:
                _cache[key] = (time.time(), result)

        if not bypass_cache:
            _misses += 1
            _total_miss_time += (time.time() - start_miss_time)

        return result
        
    except Exception as e:
        err_result = {
            "website": website,
            "title": f"Tracked Product ({website})",
            "price": None,
            "in_stock": False,
            "image_url": None,
            "error": str(e)
        }
        if not bypass_cache:
            _misses += 1
            _total_miss_time += (time.time() - start_miss_time)
        return err_result
