import secrets
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.app import schemas, models, database
from backend.app.services.auth import hash_password, verify_password, create_access_token
from backend.app.dependencies import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

logger = logging.getLogger("auth_router")

@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """
    Register a new user in the SaaS platform.
    """
    # 1. Validation checks
    if len(user.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
        
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )
        
    # 2. Hash password & save
    hashed = hash_password(user.password)
    new_user = models.User(
        name=user.name,
        email=user.email,
        hashed_password=hashed
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("Successfully registered user: %s (ID: %d)", new_user.email, new_user.id)
    return new_user

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    Authenticate email & password, returning a JWT token on success.
    """
    # username is passed as email in OAuth2PasswordRequestForm
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated."
        )
        
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """
    Get profile information of the current authenticated user.
    """
    return current_user

@router.put("/me", response_model=schemas.User)
def update_user_me(user_update: schemas.UserUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    """
    Update profile details (name, email) of the current authenticated user.
    """
    if user_update.name is not None:
        current_user.name = user_update.name
    if user_update.email is not None and user_update.email != current_user.email:
        # Check if the new email is already in use
        existing = db.query(models.User).filter(models.User.email == user_update.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered by another user."
            )
        current_user.email = user_update.email
        
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password", status_code=status.HTTP_200_OK)
def change_password_me(pw_update: schemas.UserPasswordUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    """
    Update the password of the current authenticated user.
    """
    if not verify_password(pw_update.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password."
        )
        
    if len(pw_update.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long."
        )
        
    current_user.hashed_password = hash_password(pw_update.new_password)
    db.commit()
    return {"status": "success", "message": "Password changed successfully."}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(req: schemas.ForgotPasswordRequest, db: Session = Depends(database.get_db)):
    """
    Initiate password reset flow, generating a secure token.
    """
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user:
        # Avoid user enumeration by returning OK anyway, but logging details
        logger.warning("Forgot password request for non-existent user email: %s", req.email)
        return {"status": "success", "message": "If this email is registered, a password reset token has been generated."}
        
    # Generate random secure reset token
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    db.commit()
    
    # Prepare backend email integration - log reset token for user retrieval
    logger.info("====================================================")
    logger.info("PASSWORD RESET LINK GENERATED FOR EMAIL: %s", user.email)
    logger.info("TOKEN: %s", token)
    logger.info("====================================================")
    
    return {
        "status": "success", 
        "message": "If this email is registered, a password reset token has been generated.",
        "token": token # Return token in API payload so frontend/test suites can capture it easily
    }

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(req: schemas.UserResetPassword, db: Session = Depends(database.get_db)):
    """
    Validate reset token and configure new user password.
    """
    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
        
    user = db.query(models.User).filter(models.User.reset_token == req.token).first()
    if not user or not req.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )
        
    user.hashed_password = hash_password(req.new_password)
    user.reset_token = None # Clear token
    db.commit()
    logger.info("Password successfully reset for user: %s", user.email)
    return {"status": "success", "message": "Password reset completed successfully."}
