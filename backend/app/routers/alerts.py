from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app import crud, schemas, database, models
from backend.app.dependencies import get_current_user

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"]
)

@router.get("/", response_model=List[schemas.Alert])
def read_alerts(product_id: Optional[int] = None, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if product_id is not None:
        db_product = crud.get_product(db, product_id=product_id, user_id=current_user.id)
        if not db_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return crud.get_alerts(db, product_id=product_id)
    
    # Query alerts for all products belonging to this user
    return db.query(models.Alert).join(models.Product).filter(models.Product.user_id == current_user.id).all()

@router.post("/", response_model=schemas.Alert, status_code=status.HTTP_201_CREATED)
def create_alert(alert: schemas.AlertCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    # Verify product exists and belongs to current user
    db_product = crud.get_product(db, product_id=alert.product_id, user_id=current_user.id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {alert.product_id} not found"
        )
    if not alert.email and not alert.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide at least one contact channel (email or phone)"
        )
    return crud.create_alert(db=db, alert=alert)

@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    db_alert = db.query(models.Alert).join(models.Product).filter(
        models.Alert.id == alert_id,
        models.Product.user_id == current_user.id
    ).first()
    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    crud.delete_alert(db, alert_id=alert_id)
    return
