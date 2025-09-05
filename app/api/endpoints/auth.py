from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import (
    UserResponse, TokenResponse, SSORequest, FirebaseUserResponse,
    RefreshTokenRequest, PasswordResetRequest, PasswordResetConfirm, MessageResponse,
    UpdateProfile, UsernameCheckRequest, UsernameCheckResponse,
    UpdateUsernameRequest, UpdatePhoneRequest
)
from app.services.auth_service import AuthService
from app.services.oauth_service import FirebaseOAuthService
from app.core.security import decode_token, validate_password_strength
from app.core.dependencies import get_current_user
from app.models.user import User
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Authentication"])



@router.post("/sso", response_model=FirebaseUserResponse)
async def sso_auth(request: SSORequest):
    """
    Firebase SSO Authentication - Verifies Firebase ID token
    Unified endpoint for all Firebase authentication
    """
    try:
        # Use the OAuth service for Firebase token verification (same as working endpoints)
        firebase_user = await FirebaseOAuthService.verify_firebase_token(request.id_token)
        
        if not firebase_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Firebase ID token"
            )
        
        return FirebaseUserResponse(
            uid=firebase_user["id"],
            email=firebase_user["email"],
            email_verified=firebase_user["email_verified"],
            name=firebase_user["name"],
            picture=firebase_user["picture"],
            provider=firebase_user.get("provider", "firebase"),
            additional_details=request.additional_details or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Firebase SSO authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase SSO authentication failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token
    """
    payload = decode_token(request.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    tokens = AuthService.generate_tokens(user)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserResponse.from_orm(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return UserResponse.from_orm(current_user)


@router.get("/user/{user_id}", response_model=UserResponse)
async def get_user_info(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user information by user ID
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Logout current user (invalidate tokens)
    Note: In production, you might want to blacklist the token in Redis
    """
    # Here you could add the token to a blacklist in Redis
    # For now, the client should just discard the token
    return MessageResponse(message="Successfully logged out")


@router.post("/password-reset", response_model=MessageResponse)
async def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Request password reset email
    """
    # Implementation would send email with reset token
    # For now, just return success
    return MessageResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/password-reset-confirm", response_model=MessageResponse)
async def confirm_password_reset(request: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    Confirm password reset with token
    """
    # Implementation would verify token and update password
    # For now, just validate password strength
    is_valid, error_message = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    return MessageResponse(message="Password successfully reset")


@router.post("/check-username", response_model=UsernameCheckResponse)
async def check_username_availability(
    request: UsernameCheckRequest, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if a username is available
    """
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == request.username).first()
        
        if existing_user:
            return UsernameCheckResponse(
                available=False,
                message="Username is already taken"
            )
        else:
            return UsernameCheckResponse(
                available=True,
                message="Username is available"
            )
    except Exception as e:
        logger.error(f"Username check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while checking username availability"
        )


@router.put("/update-username", response_model=UserResponse)
async def update_username(
    request: UpdateUsernameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the username for the current user
    """
    try:
        # Check if username already exists (excluding current user)
        existing_user = db.query(User).filter(
            User.username == request.username,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken"
            )
        
        # Merge the user object into the current session
        current_user = db.merge(current_user)
        
        # Update the username
        current_user.username = request.username
        
        # Update timestamp
        from datetime import datetime
        current_user.updated_at = datetime.utcnow()
        
        # Commit changes
        db.commit()
        db.refresh(current_user)
        
        return UserResponse.from_orm(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Username update error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating username"
        )


@router.put("/update-phone", response_model=UserResponse)
async def update_phone_number(
    request: UpdatePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the phone number and country code for the current user
    """
    try:
        # Check if phone number is already taken by another user
        if request.phone_number is not None and request.phone_number:
            # Phone number is already cleaned by validator
            existing_user = db.query(User).filter(
                User.phone_number == request.phone_number,
                User.country_code == request.country_code,
                User.id != current_user.id
            ).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This phone number is already registered with another account"
                )
        
        # Merge the user object into the current session
        current_user = db.merge(current_user)
        
        # Update phone number and country code
        if request.phone_number is not None:
            current_user.phone_number = request.phone_number
        
        if request.country_code is not None:
            current_user.country_code = request.country_code
        
        # Update timestamp
        from datetime import datetime
        current_user.updated_at = datetime.utcnow()
        
        # Commit changes
        db.commit()
        db.refresh(current_user)
        
        return UserResponse.from_orm(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Phone number update error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating phone number"
        )


@router.put("/update-profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile information
    """
    try:
        # Merge the user object into the current session
        current_user = db.merge(current_user)
        
        # Update basic profile fields
        if profile_data.bio is not None:
            current_user.bio = profile_data.bio
            
        if profile_data.profile_image_url is not None:
            current_user.profile_image_url = profile_data.profile_image_url
        
        # Convert instruments_taught list to JSON string for storage
        if profile_data.instruments_taught is not None:
            import json
            current_user.instruments_taught = json.dumps(profile_data.instruments_taught)
        
        # Update other fields if provided
        if profile_data.years_of_experience is not None:
            current_user.years_of_experience = profile_data.years_of_experience
        
        if profile_data.teaching_style is not None:
            current_user.teaching_style = profile_data.teaching_style
            
        if profile_data.location is not None:
            current_user.location = profile_data.location
        
        # Update timestamp
        from datetime import datetime
        current_user.updated_at = datetime.utcnow()
        
        # Commit changes
        db.commit()
        db.refresh(current_user)
        
        return UserResponse.from_orm(current_user)
        
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating profile"
        )