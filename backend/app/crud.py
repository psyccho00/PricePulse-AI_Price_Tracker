from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from backend.app import models, schemas
from backend.app.services.scraper import scrape_product, detect_website
from backend.app.services.notifier import send_email_alert
from backend.app.services.whatsapp import send_whatsapp_alert

# ==========================================
# Product CRUD
# ==========================================
def get_product(db: Session, product_id: int, user_id: Optional[int] = None) -> Optional[models.Product]:
    query = db.query(models.Product).filter(models.Product.id == product_id)
    if user_id is not None:
        query = query.filter(models.Product.user_id == user_id)
    return query.first()

def get_products(db: Session, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[models.Product]:
    query = db.query(models.Product)
    if user_id is not None:
        query = query.filter(models.Product.user_id == user_id)
    return query.offset(skip).limit(limit).all()

def create_product(db: Session, product: schemas.ProductCreate, user_id: Optional[int] = None) -> models.Product:
    # If the product name is placeholder or empty, we can try to resolve it from the initial url
    name = product.name
    initial_price = None
    initial_image_url = None
    scraped = None

    if product.initial_url:
        scraped = scrape_product(product.initial_url, bypass_cache=True)
        initial_price = scraped.get("price")
        initial_image_url = scraped.get("image_url")
        if not name or name.strip() in ("", "Pending Scrape"):
            if scraped.get("title"):
                name = scraped["title"]
            else:
                name = f"Tracked Product ({scraped.get('website', 'unknown')})"

    if not name or not name.strip():
        name = "Tracked Product"

    db_product = models.Product(
        name=name,
        category=product.category,
        image_url=initial_image_url,
        user_id=user_id
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    # Add initial URL if provided
    if product.initial_url and scraped:
        website = product.initial_website or detect_website(product.initial_url)
        db_link = models.ProductLink(
            product_id=db_product.id,
            url=product.initial_url,
            website=website,
            current_price=initial_price,
            in_stock=scraped.get("in_stock", True),
            image_url=initial_image_url,
            last_scraped_at=datetime.datetime.utcnow() if initial_price is not None else None
        )
        db.add(db_link)
        db.commit()
        db.refresh(db_link)
        
        # Seed default bank offers for this platform
        seed_default_offers(db, db_link)

        # If we got a price, record in history
        if initial_price is not None:
            db_history = models.PriceHistory(
                product_link_id=db_link.id,
                price=initial_price
            )
            db.add(db_history)
            db.commit()

    db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int) -> bool:
    db_product = get_product(db, product_id)
    if not db_product:
        return False
    db.delete(db_product)
    db.commit()
    return True

# ==========================================
# Product Link CRUD
# ==========================================
def get_product_link(db: Session, link_id: int) -> Optional[models.ProductLink]:
    return db.query(models.ProductLink).filter(models.ProductLink.id == link_id).first()

def get_product_links(db: Session, product_id: int) -> List[models.ProductLink]:
    return db.query(models.ProductLink).filter(models.ProductLink.product_id == product_id).all()

def create_product_link(db: Session, link: schemas.ProductLinkCreate) -> models.ProductLink:
    # Try scraping initial price
    scraped = scrape_product(link.url)
    current_price = scraped.get("price")
    image_url = scraped.get("image_url")
    if current_price is None:
        current_price = link.current_price

    db_link = models.ProductLink(
        product_id=link.product_id,
        url=link.url,
        website=link.website,
        current_price=current_price,
        in_stock=scraped.get("in_stock", True),
        image_url=image_url,
        last_scraped_at=datetime.datetime.utcnow() if current_price is not None else None
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    
    # Update parent product image if it is missing
    product = get_product(db, link.product_id)
    if product and not product.image_url and image_url:
        product.image_url = image_url
        db.commit()
    
    # Seed default bank offers for this platform
    seed_default_offers(db, db_link)

    if current_price is not None:
        db_history = models.PriceHistory(
            product_link_id=db_link.id,
            price=current_price
        )
        db.add(db_history)
        db.commit()
        
    return db_link

def update_product_link(db: Session, link_id: int, current_price: float, in_stock: Optional[bool] = None, image_url: Optional[str] = None, commit: bool = True) -> Optional[models.ProductLink]:
    db_link = get_product_link(db, link_id)
    if not db_link:
        return None

    db_link.current_price = current_price
    if in_stock is not None:
        db_link.in_stock = in_stock
    if image_url is not None:
        db_link.image_url = image_url
    db_link.last_scraped_at = datetime.datetime.utcnow()
    if commit:
        db.commit()

    # Update parent product image if it is missing or if this is the cheapest active link
    product = get_product(db, db_link.product_id)
    if product:
        active_prices = [l.current_price for l in product.links if l.is_active and l.current_price is not None]
        min_price = min(active_prices) if active_prices else None
        if not product.image_url or (image_url and db_link.current_price == min_price):
            if image_url:
                product.image_url = image_url
                if commit:
                    db.commit()

    # Append to price history
    db_history = models.PriceHistory(
        product_link_id=link_id,
        price=current_price
    )
    db.add(db_history)
    if commit:
        db.commit()

    # Check alerts for this product
    check_alerts_for_product(db, db_link.product_id, current_price, db_link.url)

    if commit:
        db.refresh(db_link)
    return db_link

def delete_product_link(db: Session, link_id: int) -> bool:
    db_link = get_product_link(db, link_id)
    if not db_link:
        return False
    db.delete(db_link)
    db.commit()
    return True

# ==========================================
# Price History CRUD
# ==========================================
def get_price_history(db: Session, product_link_id: int, limit: int = 100) -> List[models.PriceHistory]:
    return db.query(models.PriceHistory)\
        .filter(models.PriceHistory.product_link_id == product_link_id)\
        .order_by(models.PriceHistory.scraped_at.desc())\
        .limit(limit).all()

# ==========================================
# Alert CRUD
# ==========================================
def get_alerts(db: Session, product_id: Optional[int] = None) -> List[models.Alert]:
    if product_id is not None:
        return db.query(models.Alert).filter(models.Alert.product_id == product_id).all()
    return db.query(models.Alert).all()

def create_alert(db: Session, alert: schemas.AlertCreate) -> models.Alert:
    db_alert = models.Alert(
        product_id=alert.product_id,
        email=alert.email,
        phone=alert.phone,
        target_price=alert.target_price,
        is_active=True,
        alert_type=getattr(alert, 'alert_type', 'target_price') or 'target_price',
        alert_condition_value=getattr(alert, 'alert_condition_value', None),
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert

def delete_alert(db: Session, alert_id: int) -> bool:
    db_alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not db_alert:
        return False
    db.delete(db_alert)
    db.commit()
    return True

# ==========================================
# Helper Notification Check
# ==========================================
def check_alerts_for_product(db: Session, product_id: int, current_price: float, url: str):
    """
    Check if the current price triggers any active alerts.
    Supports multiple alert types: target_price, percentage_drop, historical_low,
    deal_score, new_historical_low, cross_store.
    All alerts remain isolated per user through the Product -> User relationship.
    """
    product = get_product(db, product_id)
    if not product:
        return

    all_active_alerts = db.query(models.Alert).filter(
        models.Alert.product_id == product_id,
        models.Alert.is_active == True,
    ).all()

    if not all_active_alerts:
        return

    # Pre-compute data needed for smart alert checks
    history = None
    historical_low = None
    previous_price = None

    def _get_history():
        nonlocal history, historical_low, previous_price
        if history is None:
            history = get_product_price_history(db, product_id)
            if history:
                sorted_h = sorted(history, key=lambda h: h.scraped_at)
                all_prices = [h.price for h in sorted_h]
                historical_low = min(all_prices)
                if len(sorted_h) >= 2:
                    previous_price = sorted_h[-2].price

    for alert in all_active_alerts:
        alert_type = getattr(alert, 'alert_type', 'target_price') or 'target_price'
        should_notify = False
        notification_msg = None

        if alert_type == 'target_price':
            # PRESERVED: exact same logic as before
            if alert.target_price >= current_price:
                should_notify = True
                notification_msg = f"Price dropped to ₹{current_price:,.2f}, below your target of ₹{alert.target_price:,.2f}!"

        elif alert_type == 'percentage_drop':
            _get_history()
            threshold_pct = alert.alert_condition_value or 10.0
            if previous_price and previous_price > 0:
                drop_pct = ((previous_price - current_price) / previous_price) * 100.0
                if drop_pct >= threshold_pct:
                    should_notify = True
                    notification_msg = f"Price dropped {drop_pct:.1f}% (₹{previous_price:,.2f} → ₹{current_price:,.2f})"

        elif alert_type == 'historical_low':
            _get_history()
            proximity_pct = alert.alert_condition_value or 5.0
            if historical_low and historical_low > 0:
                distance_pct = ((current_price - historical_low) / historical_low) * 100.0
                if distance_pct <= proximity_pct:
                    should_notify = True
                    notification_msg = f"Price ₹{current_price:,.2f} is within {distance_pct:.1f}% of historical low ₹{historical_low:,.2f}"

        elif alert_type == 'new_historical_low':
            _get_history()
            if historical_low is not None and current_price <= historical_low and previous_price is not None and current_price < previous_price:
                should_notify = True
                notification_msg = f"🏆 NEW HISTORICAL LOW! Price is now ₹{current_price:,.2f}"

        elif alert_type == 'deal_score':
            _get_history()
            threshold_score = alert.alert_condition_value or 85.0
            if history:
                try:
                    from backend.app.services.prediction import predict_future_prices
                    target_price_val = alert.target_price if alert.target_price > 0 else current_price * 0.9
                    pred = predict_future_prices(history, target_price_val, current_price)
                    ds = pred.get('deal_score', 0)
                    if ds >= threshold_score:
                        should_notify = True
                        notification_msg = f"Deal Score reached {ds}/100 (status: {pred.get('deal_status', 'N/A')})"
                except Exception:
                    pass

        elif alert_type == 'cross_store':
            # Check if another store for same product is cheaper
            active_links = [l for l in product.links if l.is_active and l.current_price is not None]
            if len(active_links) >= 2:
                cheapest = min(active_links, key=lambda l: l.current_price)
                # Find the link that corresponds to the current URL being updated
                current_link = next((l for l in active_links if l.url == url), None)
                if current_link and cheapest.id != current_link.id:
                    savings = current_price - cheapest.current_price
                    if savings > 0:
                        should_notify = True
                        notification_msg = f"{cheapest.website.title()} is cheaper at ₹{cheapest.current_price:,.2f} (save ₹{savings:,.2f})"

        # Send notification if triggered
        if should_notify:
            msg_prefix = f"[{alert_type.replace('_', ' ').title()}] " if alert_type != 'target_price' else ""
            full_msg = msg_prefix + (notification_msg or f"Alert triggered for {product.name}")

            if alert.email:
                send_email_alert(
                    to_email=alert.email,
                    product_title=f"{product.name} - {full_msg}",
                    price=current_price,
                    url=url
                )
            if alert.phone:
                send_whatsapp_alert(
                    to_phone=alert.phone,
                    product_title=f"{product.name} - {full_msg}",
                    price=current_price,
                    url=url
                )

# ==========================================
# Phase 7 Offer Seeders & CRUD Helper Functions
# ==========================================
def seed_default_offers(db: Session, link: models.ProductLink):
    """
    Seeds default payment offers based on the store link's website platform.
    """
    offers = []
    
    if link.website == "amazon":
        offers = [
            models.Offer(
                product_link_id=link.id,
                bank="HDFC",
                card_type="Credit",
                discount_type="Percentage",
                discount_value=10.0,
                min_purchase=5000.0,
                max_discount=1500.0
            ),
            models.Offer(
                product_link_id=link.id,
                bank="Amazon Pay",
                card_type="All",
                discount_type="Percentage",
                discount_value=5.0,
                min_purchase=0.0,
                max_discount=None
            ),
            models.Offer(
                product_link_id=link.id,
                bank="SBI",
                card_type="Credit",
                discount_type="Flat",
                discount_value=1000.0,
                min_purchase=10000.0,
                max_discount=1000.0
            )
        ]
    elif link.website == "flipkart":
        offers = [
            models.Offer(
                product_link_id=link.id,
                bank="ICICI",
                card_type="Credit",
                discount_type="Percentage",
                discount_value=10.0,
                min_purchase=5000.0,
                max_discount=1750.0
            ),
            models.Offer(
                product_link_id=link.id,
                bank="Axis Bank",
                card_type="Credit",
                discount_type="Percentage",
                discount_value=5.0,
                min_purchase=2000.0,
                max_discount=1000.0
            )
        ]
    elif link.website == "myntra":
        offers = [
            models.Offer(
                product_link_id=link.id,
                bank="Axis Bank",
                card_type="Credit",
                discount_type="Percentage",
                discount_value=10.0,
                min_purchase=3000.0,
                max_discount=1000.0
            ),
            models.Offer(
                product_link_id=link.id,
                bank="SBI",
                card_type="Debit",
                discount_type="Percentage",
                discount_value=10.0,
                min_purchase=4000.0,
                max_discount=500.0
            )
        ]
        
    if offers:
        db.add_all(offers)
        db.commit()

def create_offer(db: Session, offer: schemas.OfferCreate) -> models.Offer:
    db_offer = models.Offer(
        product_link_id=offer.product_link_id,
        bank=offer.bank,
        card_type=offer.card_type,
        discount_type=offer.discount_type,
        discount_value=offer.discount_value,
        min_purchase=offer.min_purchase,
        max_discount=offer.max_discount
    )
    db.add(db_offer)
    db.commit()
    db.refresh(db_offer)
    return db_offer

def get_offers_for_link(db: Session, link_id: int) -> List[models.Offer]:
    return db.query(models.Offer).filter(models.Offer.product_link_id == link_id).all()

# ==========================================
# Phase 5 Analytics Queries
# ==========================================
def get_product_price_history(db: Session, product_id: int):
    """
    Get all price history logs across all links for a product.
    """
    return db.query(
        models.PriceHistory.id,
        models.PriceHistory.product_link_id,
        models.PriceHistory.price,
        models.PriceHistory.scraped_at,
        models.ProductLink.website
    ).join(
        models.ProductLink, 
        models.PriceHistory.product_link_id == models.ProductLink.id
    ).filter(
        models.ProductLink.product_id == product_id,
        models.ProductLink.is_active == True
    ).order_by(
        models.PriceHistory.scraped_at.asc()
    ).all()

def get_historical_analytics(db: Session, product_id: int) -> Optional[dict]:
    """
    Compute overall and platform-specific price analytics.
    """
    db_product = get_product(db, product_id)
    if not db_product:
        return None
        
    history = get_product_price_history(db, product_id)
    
    if not history:
        return {
            "product_id": product_id,
            "product_name": db_product.name,
            "lowest_price": None,
            "highest_price": None,
            "average_price": None,
            "total_price_changes": 0,
            "by_website": {}
        }
        
    prices = [h.price for h in history]
    lowest = min(prices)
    highest = max(prices)
    average = sum(prices) / len(prices)
    total_changes = len(history)
    
    # Group logs by website domain
    by_web = {}
    for h in history:
        web = h.website
        if web not in by_web:
            by_web[web] = []
        by_web[web].append(h.price)
        
    by_website_stats = {}
    for web, web_prices in by_web.items():
        by_website_stats[web] = {
            "lowest_price": min(web_prices),
            "highest_price": max(web_prices),
            "average_price": sum(web_prices) / len(web_prices),
            "total_price_changes": len(web_prices)
        }
        
    return {
        "product_id": product_id,
        "product_name": db_product.name,
        "lowest_price": lowest,
        "highest_price": highest,
        "average_price": average,
        "total_price_changes": total_changes,
        "by_website": by_website_stats
    }

def get_target_price_analysis(db: Session, product_id: int, target_price: float) -> Optional[dict]:
    """
    Analyze if the product price has met the target threshold, and generate buying recommendations.
    """
    db_product = get_product(db, product_id)
    if not db_product:
        return None
        
    history = get_product_price_history(db, product_id)
    if not history:
        return {
            "product_id": product_id,
            "target_price": target_price,
            "dates_below_target": [],
            "frequency": 0.0,
            "recommendation": "No price history logged yet."
        }
        
    dates_below = [h.scraped_at for h in history if h.price <= target_price]
    frequency = len(dates_below) / len(history) if history else 0.0
    
    # Analyze recommendation based on current price status and history trends
    active_links = [l for l in db_product.links if l.is_active and l.current_price is not None]
    current_lowest = min([l.current_price for l in active_links]) if active_links else None
    
    if current_lowest is not None and current_lowest <= target_price:
        rec = "🏆 Buy Now! The current price is already at or below your target price."
    elif len(dates_below) == 0:
        all_prices = [h.price for h in history]
        min_historical = min(all_prices) if all_prices else 0.0
        if min_historical > 0 and target_price < min_historical * 0.7:
            rec = "⚠️ Target price is extremely low (less than 70% of historical lowest price). Consider adjusting it higher."
        else:
            rec = "⏳ Price has never reached your target. Buy now if urgent, or wait and see if a discount occurs."
    elif frequency > 0.3:
        rec = "⏳ Wait! Price drops below your target price frequently. Highly likely to drop again."
    else:
        rec = "⏳ Wait/Buy: Price drops below your target rarely. Consider buying if it gets close."
        
    return {
        "product_id": product_id,
        "target_price": target_price,
        "dates_below_target": dates_below,
        "frequency": frequency,
        "recommendation": rec
    }


# ==========================================
# Price Drop Analysis
# ==========================================
def get_price_drop_analysis(db: Session, product_id: int) -> Optional[dict]:
    """
    Analyze price drops for a product using existing price history.
    Detects current drop, biggest recent drop, and new historical lows.
    """
    import datetime as dt

    db_product = get_product(db, product_id)
    if not db_product:
        return None

    history = get_product_price_history(db, product_id)

    # Get current lowest price
    active_links = [l for l in db_product.links if l.is_active and l.current_price is not None]
    current_price = min(l.current_price for l in active_links) if active_links else None

    if not history or len(history) < 2:
        hist_low = history[0].price if history else current_price
        return {
            "product_id": product_id,
            "has_drop": False,
            "current_price": current_price,
            "previous_price": None,
            "absolute_drop": None,
            "percentage_drop": None,
            "is_new_historical_low": False,
            "historical_low": hist_low,
            "biggest_drop_60d": None,
            "biggest_drop_60d_pct": None,
            "drop_summary": "Insufficient price history to detect drops."
        }

    # Sort history chronologically
    sorted_history = sorted(history, key=lambda h: h.scraped_at)
    all_prices = [h.price for h in sorted_history]
    historical_low = min(all_prices)

    # Current vs previous price
    latest_price = sorted_history[-1].price
    prev_price = sorted_history[-2].price

    # Use current_price if it's more recent than history
    if current_price is not None:
        effective_current = current_price
    else:
        effective_current = latest_price

    has_drop = effective_current < prev_price
    absolute_drop = prev_price - effective_current if has_drop else None
    percentage_drop = (absolute_drop / prev_price * 100.0) if has_drop and prev_price > 0 else None

    # Check if new historical low
    is_new_historical_low = effective_current <= historical_low and effective_current < prev_price

    # Biggest drop in last 60 days
    now = dt.datetime.utcnow()
    cutoff_60d = now - dt.timedelta(days=60)
    recent_history = [h for h in sorted_history if h.scraped_at >= cutoff_60d]

    biggest_drop_60d = None
    biggest_drop_60d_pct = None
    if len(recent_history) >= 2:
        for i in range(1, len(recent_history)):
            drop = recent_history[i - 1].price - recent_history[i].price
            if drop > 0:
                if biggest_drop_60d is None or drop > biggest_drop_60d:
                    biggest_drop_60d = drop
                    biggest_drop_60d_pct = (drop / recent_history[i - 1].price * 100.0) if recent_history[i - 1].price > 0 else None

    # Build summary
    parts = []
    if has_drop:
        parts.append(f"🔥 Price dropped ₹{absolute_drop:,.2f} ({percentage_drop:.1f}%)")
        if is_new_historical_low:
            parts.append("🏆 NEW HISTORICAL LOW!")
        if biggest_drop_60d is not None and absolute_drop is not None and absolute_drop >= biggest_drop_60d:
            parts.append("This is the biggest price drop in the last 60 days.")
    else:
        parts.append("No price drop detected in the most recent update.")

    return {
        "product_id": product_id,
        "has_drop": has_drop,
        "current_price": effective_current,
        "previous_price": prev_price,
        "absolute_drop": round(absolute_drop, 2) if absolute_drop else None,
        "percentage_drop": round(percentage_drop, 2) if percentage_drop else None,
        "is_new_historical_low": is_new_historical_low,
        "historical_low": historical_low,
        "biggest_drop_60d": round(biggest_drop_60d, 2) if biggest_drop_60d else None,
        "biggest_drop_60d_pct": round(biggest_drop_60d_pct, 2) if biggest_drop_60d_pct else None,
        "drop_summary": " ".join(parts)
    }


# ==========================================
# Product Matching
# ==========================================
def find_matching_products(db: Session, product_id: int, user_id: int) -> Optional[dict]:
    """
    Find products that may be the same item across different stores.
    Returns suggestions only — does NOT auto-merge or auto-link.
    """
    from backend.app.services.product_matcher import match_products

    source_product = get_product(db, product_id, user_id=user_id)
    if not source_product:
        return None

    # Build source product dict
    source_dict = {
        "id": source_product.id,
        "name": source_product.name,
        "links": [
            {
                "url": l.url,
                "website": l.website,
                "current_price": l.current_price,
                "is_active": l.is_active,
            }
            for l in source_product.links
        ],
    }

    # Get all other products for this user
    all_products = get_products(db, user_id=user_id)
    candidate_dicts = []
    for p in all_products:
        if p.id == product_id:
            continue
        candidate_dicts.append({
            "id": p.id,
            "name": p.name,
            "links": [
                {
                    "url": l.url,
                    "website": l.website,
                    "current_price": l.current_price,
                    "is_active": l.is_active,
                }
                for l in p.links
            ],
        })

    matches = match_products(source_dict, candidate_dicts)

    return {
        "source_product_id": source_product.id,
        "source_product_name": source_product.name,
        "matches": matches,
    }

