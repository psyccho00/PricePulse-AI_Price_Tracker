import datetime
import logging
import math
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("prediction_engine")

# Configurable Weights for AI Buy Score (must sum to 1.0 or will be normalized)
BUY_SCORE_WEIGHTS = {
    "price_vs_average": 0.20,
    "price_vs_lowest": 0.25,
    "target_price_distance": 0.25,
    "trend": 0.15,
    "historical_success_rate": 0.15
}

def calculate_linear_regression(history: List[Tuple[datetime.datetime, float]]) -> Tuple[float, float, float]:
    """
    Fits y = mx + c using Ordinary Least Squares.
    Returns: (slope, intercept, r_squared)
    """
    n = len(history)
    if n < 2:
        return 0.0, 0.0, 0.0
        
    t0 = history[0][0]
    
    # Convert timestamps to float days from t0
    x = []
    y = []
    for t, p in history:
        days = (t - t0).total_seconds() / 86400.0
        x.append(days)
        y.append(p)
        
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    num = 0.0
    den = 0.0
    for i in range(n):
        num += (x[i] - mean_x) * (y[i] - mean_y)
        den += (x[i] - mean_x) ** 2
        
    if den == 0.0:
        # All check points are at the exact same timestamp
        return 0.0, mean_y, 1.0
        
    slope = num / den
    intercept = mean_y - slope * mean_x
    
    # Calculate R-squared (Coefficient of Determination)
    ss_tot = sum((y_i - mean_y) ** 2 for y_i in y)
    ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
    
    if ss_tot == 0.0:
        r_squared = 1.0 if ss_res == 0.0 else 0.0
    else:
        r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot)))
        
    return slope, intercept, r_squared

def calculate_wma(prices: List[float]) -> float:
    """
    Computes the Weighted Moving Average (WMA) of a price list.
    Prioritizes more recent observations with linear weights.
    """
    k = min(5, len(prices))
    if k == 0:
        return 0.0
    sub_prices = prices[-k:]
    weights = list(range(1, k + 1))
    weight_sum = sum(weights)
    weighted_sum = sum(w * p for w, p in zip(weights, sub_prices))
    return weighted_sum / weight_sum

def predict_future_prices(
    history_logs: List[Any], 
    target_price: float, 
    current_price: Optional[float]
) -> Dict[str, Any]:
    """
    Predicts future prices using WMA and Linear Trend Regression,
    calculates AI Buy Score, Smart Recommendations, and Target Probability.
    All metrics include human-readable explainable rationales.
    """
    # 1. Parse history logs
    history_tuples = []
    prices = []
    for h in history_logs:
        dt = h.scraped_at if hasattr(h, "scraped_at") else h.get("scraped_at")
        p = h.price if hasattr(h, "price") else h.get("price")
        if isinstance(dt, str):
            dt = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        history_tuples.append((dt, p))
        prices.append(p)
        
    # Sort chronologically
    history_tuples.sort(key=lambda x: x[0])
    n = len(prices)
    
    # Handle baseline parameters
    if current_price is None:
        if prices:
            current_price = prices[-1]
        else:
            current_price = 0.0

    # 2. Forecasting Model: WMA + LTR
    slope = 0.0
    intercept = 0.0
    r_squared = 0.0
    
    if n >= 2:
        slope, intercept, r_squared = calculate_linear_regression(history_tuples)
        
    # Calculate days since t0
    t0 = history_tuples[0][0] if history_tuples else datetime.datetime.utcnow()
    now = datetime.datetime.utcnow()
    x_now = (now - t0).total_seconds() / 86400.0
    
    # Linear Trend Regression forecasts
    ltr_tomorrow = max(0.0, slope * (x_now + 1) + intercept) if n >= 2 else current_price
    ltr_next_week = max(0.0, slope * (x_now + 7) + intercept) if n >= 2 else current_price
    
    # Weighted Moving Average forecasts
    wma_val = calculate_wma(prices) if prices else current_price
    wma_tomorrow = wma_val
    wma_next_week = wma_val
    
    # Combined forecasts
    pred_tomorrow = round((ltr_tomorrow + wma_tomorrow) / 2.0, 2)
    pred_next_week = round((ltr_next_week + wma_next_week) / 2.0, 2)
    pred_30d = round((max(0.0, slope * (x_now + 30) + intercept) + wma_val) / 2.0, 2) if n >= 2 else current_price

    # 3. Volatility & Prediction Confidence
    avg_price = sum(prices) / n if n > 0 else current_price
    lowest_price = min(prices) if prices else current_price
    highest_price = max(prices) if prices else current_price
    
    sd = 0.0
    if n > 1:
        variance = sum((x - avg_price) ** 2 for x in prices) / (n - 1)
        sd = math.sqrt(variance)
        
    volatility_pct = (sd / avg_price * 100.0) if avg_price > 0 else 0.0
    
    # Determine confidence levels and reasons
    if n < 3:
        confidence = "Low"
        confidence_pct = 15.0 if n == 1 else 30.0
        confidence_explanation = f"Low confidence due to small price history (only {n} sample point(s) recorded)."
    else:
        # Confidence scales based on R-squared (if non-zero) and standard deviation stability
        base_conf = max(20.0, min(95.0, r_squared * 60.0 + min(35.0, n * 5.0)))
        if volatility_pct > 20.0:
            base_conf *= 0.8
        confidence_pct = round(base_conf, 1)
        
        if confidence_pct >= 75.0:
            confidence = "High"
        elif confidence_pct >= 45.0:
            confidence = "Moderate"
        else:
            confidence = "Low"
            
        trend_direction_desc = "falling" if slope < -0.05 * current_price / 30 else "rising" if slope > 0.05 * current_price / 30 else "stable"
        confidence_explanation = (
            f"Based on {n} historical observations, {trend_direction_desc} trend (slope: {slope:.2f} INR/day), "
            f"and {'low' if volatility_pct < 10.0 else 'moderate' if volatility_pct < 20.0 else 'high'} price volatility ({volatility_pct:.1f}%)."
        )

    # 4. Trend Detection
    trend_threshold = 0.05 * current_price / 30.0 if current_price > 0 else 0.5
    if slope > trend_threshold:
        trend_direction = "Rising trend"
        trend_conf = r_squared
    elif slope < -trend_threshold:
        trend_direction = "Falling trend"
        trend_conf = r_squared
    else:
        trend_direction = "Stable trend"
        trend_conf = 1.0 - (volatility_pct / 100.0) if volatility_pct < 100.0 else 0.0
        
    trend_confidence_pct = round(max(10.0, min(95.0, trend_conf * 100.0)), 1) if n >= 2 else 50.0

    times_target_reached = sum(1 for p in prices if p <= target_price)
    historical_success_rate = round((times_target_reached / n * 100.0), 1) if n > 0 else 0.0
    target_probability_pct = historical_success_rate
    if current_price <= target_price:
        target_probability_pct = 100.0

    # Estimate Wait Time based on intervals between target hits
    estimated_wait_time_desc = "Undetermined (No historical drops / upward trend)"
    wait_days_min = 0
    wait_days_max = 0
    
    if current_price <= target_price:
        estimated_wait_time_desc = "0 days (Target price already met!)"
    elif times_target_reached > 0 and n >= 2:
        # Calculate span of logs
        span_seconds = (history_tuples[-1][0] - history_tuples[0][0]).total_seconds()
        span_days = max(1.0, span_seconds / 86400.0)
        avg_days_between_hits = span_days / times_target_reached
        wait_days_min = max(1, int(avg_days_between_hits * 0.8))
        wait_days_max = max(2, int(avg_days_between_hits * 1.2))
        estimated_wait_time_desc = f"{wait_days_min}–{wait_days_max} days"
    elif slope < 0.0:
        # Project based on linear trend regression
        days_to_target = (target_price - current_price) / slope
        if days_to_target > 0:
            wait_days_min = max(1, int(days_to_target * 0.8))
            wait_days_max = max(2, int(days_to_target * 1.2))
            estimated_wait_time_desc = f"{wait_days_min}–{wait_days_max} days"

    # Probability reasons
    prob_reasons = [
        f"Target Price: INR {target_price:,.2f}",
        f"Historical Observations: {n}",
        f"Times Target Reached: {times_target_reached}"
    ]

    # 6. Configurable AI Buy Score (0-100)
    # Price vs Average Score
    if current_price <= avg_price:
        s_avg = 50.0 + 50.0 * (avg_price - current_price) / avg_price if avg_price > 0 else 50.0
    else:
        s_avg = max(0.0, 50.0 - 100.0 * (current_price - avg_price) / avg_price) if avg_price > 0 else 50.0
        
    # Price vs Lowest Score
    if current_price <= lowest_price:
        s_lowest = 100.0
    else:
        s_lowest = max(0.0, 100.0 * (1.0 - 2.0 * (current_price - lowest_price) / lowest_price)) if lowest_price > 0 else 100.0
        
    # Target Price Distance Score
    if current_price <= target_price:
        s_target = 100.0
    elif target_price > 0:
        s_target = max(0.0, 100.0 * (1.0 - 3.0 * (current_price - target_price) / target_price))
    else:
        s_target = 50.0
        
    # Trend Score
    if trend_direction == "Falling trend":
        s_trend = 100.0
    elif trend_direction == "Stable trend":
        s_trend = 50.0
    else:
        s_trend = 0.0
        
    # Success Rate Score
    s_success = target_probability_pct
    
    sub_scores = {
        "price_vs_average": s_avg,
        "price_vs_lowest": s_lowest,
        "target_price_distance": s_target,
        "trend": s_trend,
        "historical_success_rate": s_success
    }
    
    # Calculate Buy Score with weights
    w_sum = sum(BUY_SCORE_WEIGHTS.values())
    if w_sum > 0:
        buy_score = sum(BUY_SCORE_WEIGHTS[k] * sub_scores[k] for k in BUY_SCORE_WEIGHTS) / w_sum
    else:
        buy_score = 50.0
        
    buy_score = max(0, min(100, int(round(buy_score))))
    star_rating = "★" * max(1, min(5, math.ceil(buy_score / 20.0)))
    
    # Explanation reasons for the Buy Score
    buy_score_reasons = []
    if current_price < avg_price:
        pct = (avg_price - current_price) / avg_price * 100.0 if avg_price > 0 else 0.0
        buy_score_reasons.append(f"✔ Current price is {pct:.1f}% below historical average")
    elif current_price > avg_price:
        pct = (current_price - avg_price) / avg_price * 100.0 if avg_price > 0 else 0.0
        buy_score_reasons.append(f"❌ Current price is {pct:.1f}% above historical average")
    else:
        buy_score_reasons.append("✔ Current price matches historical average")

    if current_price <= lowest_price:
        buy_score_reasons.append("✔ Price is at its historical lowest level")
    elif current_price <= lowest_price * 1.05:
        buy_score_reasons.append("✔ Price is close to historical lowest (within 5%)")
    else:
        pct = (current_price - lowest_price) / lowest_price * 100.0 if lowest_price > 0 else 0.0
        buy_score_reasons.append(f"❌ Price is {pct:.1f}% higher than historical lowest")

    if current_price <= target_price:
        buy_score_reasons.append(f"✔ Price is at or below target (saved ₹{target_price - current_price:,.2f})")
    elif current_price <= target_price * 1.05:
        buy_score_reasons.append("✔ Price is close to user target (within 5%)")
    else:
        pct = (current_price - target_price) / target_price * 100.0 if target_price > 0 else 0.0
        buy_score_reasons.append(f"❌ Price is {pct:.1f}% above target")

    if trend_direction == "Falling trend":
        buy_score_reasons.append("✔ Historical trend is decreasing (falling)")
    elif trend_direction == "Rising trend":
        buy_score_reasons.append("❌ Historical trend is increasing (rising)")
    else:
        buy_score_reasons.append("✔ Historical trend is stable")

    if target_probability_pct >= 50.0:
        buy_score_reasons.append(f"✔ Product frequently reaches this price ({target_probability_pct:.1f}% success rate)")
    elif target_probability_pct > 0.0:
        buy_score_reasons.append(f"✔ Product occasionally reaches target ({target_probability_pct:.1f}% success rate)")
    else:
        buy_score_reasons.append("❌ Product has never reached target price historically")

    # 7. Smart Recommendations
    wait_period_desc = "N/A"
    if buy_score >= 80:
        smart_rec = "BUY NOW"
        smart_rec_reason = f"🏆 Immediate Purchase: Current price of INR {current_price:.2f} is exceptionally close to target and at its historical lowest. Don't wait."
    elif buy_score >= 60:
        smart_rec = "GOOD DEAL"
        smart_rec_reason = f"🎯 Good Deal: Price is below historical average (INR {avg_price:.2f}) and near target. Worth grabbing now if you need the product soon."
    elif buy_score >= 35:
        smart_rec = "WAIT"
        potential_saving = current_price - lowest_price if current_price > lowest_price else 0.0
        smart_rec_reason = f"⏳ Historically, this product drops another INR {potential_saving:.2f} to hit its peak discount. Waiting is recommended."
        wait_period_desc = estimated_wait_time_desc
    else:
        smart_rec = "NOT RECOMMENDED"
        smart_rec_reason = f"❌ The price is currently near its historical peak (INR {highest_price:.2f}). We advise against buying now; wait for a correction."
        wait_period_desc = "Undetermined (>30 days)"

    # 8. Deal Score (separate from AI Buy Score)
    # Deal Score is purely about where current price sits in historical range
    # AI Buy Score factors in target price and recommendation logic
    if highest_price > lowest_price:
        # Price percentile: 0% = at historical low, 100% = at historical high
        price_percentile = (current_price - lowest_price) / (highest_price - lowest_price) * 100.0
        price_percentile = max(0.0, min(100.0, price_percentile))
    else:
        price_percentile = 50.0  # No range means typical

    # Deal score: inverse of percentile with avg adjustment
    # Lower current price relative to history = higher deal score
    ds_percentile_score = max(0.0, 100.0 - price_percentile)

    # Distance from average bonus
    if avg_price > 0 and current_price < avg_price:
        ds_avg_bonus = min(20.0, ((avg_price - current_price) / avg_price) * 100.0)
    else:
        ds_avg_bonus = 0.0

    # Trend bonus
    if trend_direction == "Falling trend":
        ds_trend_bonus = 10.0
    elif trend_direction == "Rising trend":
        ds_trend_bonus = -10.0
    else:
        ds_trend_bonus = 0.0

    deal_score_raw = ds_percentile_score * 0.7 + ds_avg_bonus + ds_trend_bonus
    deal_score = max(0, min(100, int(round(deal_score_raw))))

    # Deal Status mapping
    if deal_score >= 75:
        deal_status = "LOW"
    elif deal_score >= 40:
        deal_status = "TYPICAL"
    else:
        deal_status = "HIGH"

    # Deal explanation
    deal_parts = []
    if current_price <= lowest_price:
        deal_parts.append("Price is at its historical lowest")
    elif price_percentile < 25:
        deal_parts.append(f"Price is in the bottom 25% of historical range")
    elif price_percentile < 50:
        deal_parts.append(f"Price is below the historical midpoint")
    elif price_percentile < 75:
        deal_parts.append(f"Price is above the historical midpoint")
    else:
        deal_parts.append(f"Price is in the top 25% of historical range")

    if current_price < avg_price:
        pct_below = ((avg_price - current_price) / avg_price * 100.0) if avg_price > 0 else 0
        deal_parts.append(f"{pct_below:.1f}% below historical average (₹{avg_price:,.0f})")
    elif current_price > avg_price:
        pct_above = ((current_price - avg_price) / avg_price * 100.0) if avg_price > 0 else 0
        deal_parts.append(f"{pct_above:.1f}% above historical average (₹{avg_price:,.0f})")

    deal_explanation = ". ".join(deal_parts) + "."

    return {
        "predicted_price_7d": pred_next_week,
        "predicted_price_14d": pred_next_week,  # Legacy field keep compatible
        "predicted_price_30d": pred_30d,         # Legacy field keep compatible
        "slope": round(slope, 4),
        "r_squared": round(r_squared, 4),
        "confidence": confidence,
        "estimated_date_reached": now + datetime.timedelta(days=wait_days_max) if wait_days_max > 0 else None,
        "recommendation": smart_rec,  # Replaces legacy rec with BUY NOW, WAIT, etc.
        "rationale": smart_rec_reason,
        
        # New AI Upgrade fields
        "ai_buy_score": buy_score,
        "star_rating": star_rating,
        "buy_score_reasons": buy_score_reasons,
        "predicted_price_tomorrow": pred_tomorrow,
        "predicted_price_next_week": pred_next_week,
        "prediction_confidence_pct": confidence_pct,
        "prediction_confidence_explanation": confidence_explanation,
        "smart_recommendation": smart_rec,
        "smart_recommendation_reason": smart_rec_reason,
        "smart_recommendation_wait_days": wait_period_desc,
        "target_probability_pct": target_probability_pct,
        "target_probability_reasons": prob_reasons,
        "estimated_wait_time_desc": estimated_wait_time_desc,
        "historical_success_rate_pct": historical_success_rate,
        "trend_direction": trend_direction,
        "trend_confidence_pct": trend_confidence_pct,

        # Deal Score fields (separate from AI Buy Score)
        "deal_score": deal_score,
        "deal_status": deal_status,
        "deal_explanation": deal_explanation,
        "price_percentile": round(price_percentile, 1),
    }
