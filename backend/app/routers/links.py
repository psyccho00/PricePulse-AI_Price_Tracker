from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app import crud, schemas, database, models
from backend.app.dependencies import get_current_user

router = APIRouter(
    prefix="/links",
    tags=["links"]
)

@router.post("/", response_model=schemas.ProductLink, status_code=status.HTTP_201_CREATED)
def create_link(link: schemas.ProductLinkCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    # Verify product exists and belongs to current user
    db_product = crud.get_product(db, product_id=link.product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {link.product_id} not found"
        )
    return crud.create_product_link(db=db, link=link)

@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_link = crud.get_product_link(db, link_id=link_id)
    if not db_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    db_product = crud.get_product(db, product_id=db_link.product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    crud.delete_product_link(db, link_id=link_id)
    return

@router.post("/{link_id}/price", response_model=schemas.ProductLink)
def record_test_price(link_id: int, price: float, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_link = crud.get_product_link(db, link_id=link_id)
    if not db_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    db_product = crud.get_product(db, product_id=db_link.product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    db_link = crud.update_product_link(db, link_id=link_id, current_price=price)
    return db_link

@router.post("/{link_id}/check", response_model=schemas.ProductLink)
def check_link_price_now(link_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_link = crud.get_product_link(db, link_id=link_id)
    if not db_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    db_product = crud.get_product(db, product_id=db_link.product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    from backend.app.services.scraper import scrape_product
    scraped = scrape_product(db_link.url, bypass_cache=True)
    price = scraped.get("price")
    
    if price is not None:
        db_link = crud.update_product_link(db, link_id=link_id, current_price=price, in_stock=scraped.get("in_stock", True), image_url=scraped.get("image_url"))
        
        # If the product name was a generic placeholder, update it with the scraped title
        if scraped.get("title") and scraped["title"] != "Amazon Product":
            if "Tracked Product" in db_product.name or db_product.name == "Pending Scrape":
                db_product.name = scraped["title"]
                db.commit()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scraper could not retrieve price: {scraped.get('error') or 'Check page layout'}"
        )
    return db_link

@router.get("/{link_id}/history", response_model=List[schemas.PriceHistory])
def read_price_history(link_id: int, limit: int = 100, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_link = crud.get_product_link(db, link_id=link_id)
    if not db_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    db_product = crud.get_product(db, product_id=db_link.product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    return crud.get_price_history(db, product_link_id=link_id, limit=limit)
