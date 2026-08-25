from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app import crud, schemas, database, models
from backend.app.dependencies import get_current_user

router = APIRouter(
    prefix="/products",
    tags=["products"]
)

@router.get("/", response_model=List[schemas.Product])
def read_products(skip: int = 0, limit: int = 100, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    products = crud.get_products(db, user_id=current_user.id, skip=skip, limit=limit)
    return products

@router.get("/{product_id}", response_model=schemas.ProductDetail)
def read_product(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if db_product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return db_product

@router.post("/", response_model=schemas.Product, status_code=status.HTTP_201_CREATED)
def create_product(product: schemas.ProductCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    return crud.create_product(db=db, product=product, user_id=current_user.id)

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if db_product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    crud.delete_product(db, product_id=product_id)
    return

@router.get("/{product_id}/comparison", response_model=schemas.PriceComparisonResponse)
def get_price_comparison(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    active_links = [link for link in db_product.links if link.is_active]
    
    comparisons = []
    lowest_price = None
    highest_price = None
    best_platform = None
    best_platform_in_stock = False
    
    # First find the lowest price among in-stock links to determine the best deal
    in_stock_prices = [link.current_price for link in active_links if link.in_stock and link.current_price is not None]
    
    if in_stock_prices:
        lowest_price = min(in_stock_prices)
        highest_price = max(in_stock_prices)
    else:
        # Fallback to any active price if none are marked in stock (or all are out of stock)
        all_prices = [link.current_price for link in active_links if link.current_price is not None]
        if all_prices:
            lowest_price = min(all_prices)
            highest_price = max(all_prices)

    # Determine best platform
    if lowest_price is not None:
        for link in active_links:
            if link.current_price == lowest_price:
                # Prioritize in-stock deal
                if not best_platform or (link.in_stock and not best_platform_in_stock):
                    best_platform = link.website
                    best_platform_in_stock = link.in_stock

    for link in active_links:
        price = link.current_price
        is_best = (price == lowest_price) if price is not None and lowest_price is not None else False
        
        # Calculate savings versus buying at this platform's price compared to the best deal
        savings_vs_this = 0.0
        if price is not None and lowest_price is not None:
            savings_vs_this = max(0.0, price - lowest_price)
            
        comparisons.append(
            schemas.PlatformComparison(
                platform=link.website,
                price=price,
                url=link.url,
                in_stock=link.in_stock,
                is_best_deal=is_best,
                savings_vs_this=savings_vs_this
            )
        )
    
    savings_amount = 0.0
    if highest_price is not None and lowest_price is not None:
        savings_amount = max(0.0, highest_price - lowest_price)
        
    return schemas.PriceComparisonResponse(
        product_id=product_id,
        product_name=db_product.name,
        comparisons=comparisons,
        best_platform=best_platform,
        lowest_price=lowest_price,
        highest_price=highest_price,
        savings_amount=savings_amount
    )

@router.get("/{product_id}/payment-optimization", response_model=schemas.PaymentOptimizationResponse)
def optimize_payment(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
        
    active_links = [l for l in db_product.links if l.is_active and l.current_price is not None]
    
    platform_prices = {}
    platform_effective_prices = {}
    
    best_platform = None
    best_payment_method = None
    lowest_effective = None
    listed_price = None
    
    for link in active_links:
        price = link.current_price
        platform_prices[link.website] = price
        
        # Get all bank offers for this product link
        offers = crud.get_offers_for_link(db, link.id)
        
        link_best_price = price
        link_best_method = "Standard Price (No Offer)"
        
        for offer in offers:
            if price >= offer.min_purchase:
                # Calculate discount
                if offer.discount_type == "Percentage":
                    discount = price * (offer.discount_value / 100.0)
                else:
                    discount = offer.discount_value
                    
                if offer.max_discount is not None:
                    discount = min(discount, offer.max_discount)
                    
                eff_price = max(0.0, price - discount)
                if eff_price < link_best_price:
                    link_best_price = eff_price
                    link_best_method = f"{offer.bank} {offer.card_type} card"
                    
        platform_effective_prices[link.website] = link_best_price
        
        # Track global best effective price
        if lowest_effective is None or link_best_price < lowest_effective:
            lowest_effective = link_best_price
            best_platform = link.website
            best_payment_method = link_best_method
            listed_price = price
            
    savings = 0.0
    if listed_price is not None and lowest_effective is not None:
        savings = max(0.0, listed_price - lowest_effective)
        
    return schemas.PaymentOptimizationResponse(
        product_id=product_id,
        product_name=db_product.name,
        listed_price=listed_price,
        best_platform=best_platform,
        best_payment_method=best_payment_method,
        final_effective_price=lowest_effective,
        savings=savings,
        platform_prices=platform_prices,
        platform_effective_prices=platform_effective_prices
    )


@router.get("/{product_id}/match-suggestions", response_model=schemas.ProductMatchResponse)
def get_product_match_suggestions(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    """
    Find products that may be the same item across different stores.
    Returns suggestions ONLY — does NOT auto-merge or auto-link.
    The user must manually decide whether to link a matched product.
    """
    result = crud.find_matching_products(db, product_id=product_id, user_id=current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return result
