from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import math
from backend.app import crud, schemas, database, models
from backend.app.dependencies import get_current_user

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)

@router.get("/{product_id}/history", response_model=List[schemas.PriceHistoryEntry])
def read_product_price_history(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return crud.get_product_price_history(db, product_id=product_id)

@router.get("/{product_id}/summary", response_model=schemas.PriceAnalyticsResponse)
def read_product_analytics_summary(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    analytics = crud.get_historical_analytics(db, product_id=product_id)
    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product has no tracking links"
        )
    return analytics

@router.get("/{product_id}/target-analysis", response_model=schemas.TargetAnalysisResponse)
def read_target_price_analysis(product_id: int, target_price: float, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    analysis = crud.get_target_price_analysis(db, product_id=product_id, target_price=target_price)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not generate analysis"
        )
    return analysis

@router.get("/{product_id}/prediction", response_model=schemas.PricePredictionResponse)
def get_price_prediction(product_id: int, target_price: float, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    history = crud.get_product_price_history(db, product_id=product_id)
    
    active_links = [l for l in db_product.links if l.is_active and l.current_price is not None]
    current_price = min([l.current_price for l in active_links]) if active_links else None
    
    from backend.app.services.prediction import predict_future_prices
    prediction = predict_future_prices(history, target_price, current_price)
    
    prediction["product_id"] = product_id
    prediction["target_price"] = target_price
    prediction["current_price"] = current_price
    
    return prediction

@router.get("/portfolio-ai-summary", response_model=schemas.PortfolioAISummaryResponse)
def read_portfolio_ai_summary(current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    products = crud.get_products(db, user_id=current_user.id)
    if not products:
        return schemas.PortfolioAISummaryResponse(
            best_product_to_buy=None,
            product_expected_to_drop_most=None,
            highest_potential_savings=None,
            highest_volatility=None,
            portfolio_ai_score=0.0,
            average_buy_score=0.0
        )
        
    entries = []
    
    # Track metrics for comparison
    best_product = None
    best_score = -1
    
    max_drop = -999999.0
    drop_product = None
    
    max_savings = -1.0
    savings_product = None
    
    max_volatility = -1.0
    volatility_product = None
    
    total_buy_score = 0.0
    products_scored_count = 0
    
    from backend.app.services.prediction import predict_future_prices
    
    for p in products:
        # Get active current price
        active_links = [l for l in p.links if l.is_active and l.current_price is not None]
        if not active_links:
            continue
        current_price = min(l.current_price for l in active_links)
        
        # Get alerts (target price)
        alerts = [a for a in p.alerts if a.is_active]
        target_price = alerts[0].target_price if alerts else current_price * 0.9  # fallback
        
        # Get price history
        history = crud.get_product_price_history(db, product_id=p.id)
        
        # Calculate prediction
        pred = predict_future_prices(history, target_price, current_price)
        
        buy_score = pred.get("ai_buy_score", 50)
        smart_rec = pred.get("smart_recommendation", "WAIT")
        star_rating = pred.get("star_rating", "★★★")
        
        total_buy_score += buy_score
        products_scored_count += 1
        
        entry = schemas.ProductAISummaryEntry(
            product_id=p.id,
            product_name=p.name,
            ai_buy_score=buy_score,
            star_rating=star_rating,
            smart_recommendation=smart_rec,
            current_price=current_price,
            target_price=target_price if alerts else None
        )
        entries.append(entry)
        
        # 1. Best product to buy today (highest Buy Score)
        if buy_score > best_score:
            best_score = buy_score
            best_product = entry
            
        # 2. Product expected to drop the most (largest predicted price drop next week)
        predicted_next_week = pred.get("predicted_price_next_week", current_price)
        expected_drop = current_price - predicted_next_week
        if expected_drop > max_drop:
            max_drop = expected_drop
            drop_product = entry
            
        # 3. Highest potential savings (difference between current price and target price)
        if current_price > target_price:
            savings = current_price - target_price
            if savings > max_savings:
                max_savings = savings
                savings_product = entry
                
        # 4. Highest volatility (coefficient of variation of price history)
        history_prices = [h.price for h in history]
        if len(history_prices) >= 2:
            mean_p = sum(history_prices) / len(history_prices)
            var_p = sum((x - mean_p) ** 2 for x in history_prices) / (len(history_prices) - 1)
            std_p = math.sqrt(var_p)
            volatility = std_p / mean_p if mean_p > 0 else 0.0
            if volatility > max_volatility:
                max_volatility = volatility
                volatility_product = entry
                
    if products_scored_count == 0:
        return schemas.PortfolioAISummaryResponse(
            best_product_to_buy=None,
            product_expected_to_drop_most=None,
            highest_potential_savings=None,
            highest_volatility=None,
            portfolio_ai_score=0.0,
            average_buy_score=0.0
        )
        
    avg_buy_score = total_buy_score / products_scored_count
    
    return schemas.PortfolioAISummaryResponse(
        best_product_to_buy=best_product,
        product_expected_to_drop_most=drop_product if max_drop > 0 else None,
        highest_potential_savings=savings_product,
        highest_volatility=volatility_product,
        portfolio_ai_score=round(avg_buy_score, 1),
        average_buy_score=round(avg_buy_score, 1)
    )


@router.get("/{product_id}/price-drop", response_model=schemas.PriceDropResponse)
def get_price_drop_analysis(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    result = crud.get_price_drop_analysis(db, product_id=product_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not generate price drop analysis"
        )
    return result


@router.get("/{product_id}/deal-score")
def get_deal_score(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    """
    Returns Deal Score metrics (separate from AI Buy Score).
    Deal Score = historical price quality indicator.
    AI Buy Score = overall buying recommendation.
    """
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    history = crud.get_product_price_history(db, product_id=product_id)

    active_links = [l for l in db_product.links if l.is_active and l.current_price is not None]
    current_price = min([l.current_price for l in active_links]) if active_links else None

    # Use the default target price from active alerts, or fallback
    alerts = [a for a in db_product.alerts if a.is_active]
    target_price = alerts[0].target_price if alerts else (current_price * 0.9 if current_price else 0.0)

    from backend.app.services.prediction import predict_future_prices
    prediction = predict_future_prices(history, target_price, current_price)

    return {
        "product_id": product_id,
        "product_name": db_product.name,
        "current_price": current_price,
        "deal_score": prediction.get("deal_score", 0),
        "deal_status": prediction.get("deal_status", "TYPICAL"),
        "deal_explanation": prediction.get("deal_explanation", ""),
        "price_percentile": prediction.get("price_percentile", 50.0),
        "ai_buy_score": prediction.get("ai_buy_score", 50),
        "star_rating": prediction.get("star_rating", "★★★"),
    }

