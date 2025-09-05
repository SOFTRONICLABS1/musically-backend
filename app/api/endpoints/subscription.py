from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.subscription import (
    SubscriptionRequest, UnsubscribeRequest, SubscriptionResponse,
    SubscriptionListResponse, SubscriptionStatusResponse
)
from app.schemas.auth import MessageResponse
from app.services.subscription_service import SubscriptionService
from app.core.dependencies import get_current_user
from app.models.user import User, UserSubscription
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Subscriptions"])


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe_to_user(
    request: SubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Subscribe to a user
    """
    try:
        subscription = SubscriptionService.subscribe_to_user(
            db=db,
            subscriber_id=current_user.id,
            owner_id=request.owner_user_id,
            subscription_type=request.subscription_type
        )
        
        # Add user info for response
        subscription_data = SubscriptionResponse.from_orm(subscription)
        subscription_data.owner_username = subscription.owner.signup_username
        subscription_data.subscriber_username = subscription.subscriber.signup_username
        
        return subscription_data
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Subscribe error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while subscribing"
        )


@router.post("/unsubscribe", response_model=MessageResponse)
async def unsubscribe_from_user(
    request: UnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unsubscribe from a user
    """
    try:
        success = SubscriptionService.unsubscribe_from_user(
            db=db,
            subscriber_id=current_user.id,
            owner_id=request.owner_user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        return MessageResponse(message="Successfully unsubscribed")
        
    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unsubscribing"
        )


@router.get("/status/{owner_user_id}", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    owner_user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user is subscribed to a specific user
    """
    subscription = SubscriptionService.get_subscription_status(
        db=db,
        subscriber_id=current_user.id,
        owner_id=owner_user_id
    )
    
    if subscription:
        subscription_data = SubscriptionResponse.from_orm(subscription)
        subscription_data.owner_username = subscription.owner.signup_username
        subscription_data.subscriber_username = subscription.subscriber.signup_username
        
        return SubscriptionStatusResponse(
            is_subscribed=True,
            subscription=subscription_data
        )
    
    return SubscriptionStatusResponse(is_subscribed=False)


@router.get("/my-subscriptions", response_model=SubscriptionListResponse)
async def get_my_subscriptions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of users that current user is subscribed to
    """
    try:
        subscriptions, total = SubscriptionService.get_user_subscriptions(
            db=db,
            user_id=current_user.id,
            page=page,
            per_page=per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        # Add user info to each subscription
        subscription_responses = []
        for subscription in subscriptions:
            subscription_data = SubscriptionResponse.from_orm(subscription)
            subscription_data.owner_username = subscription.owner.signup_username
            subscription_data.subscriber_username = subscription.subscriber.signup_username
            subscription_responses.append(subscription_data)
        
        return SubscriptionListResponse(
            subscriptions=subscription_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get subscriptions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching subscriptions"
        )


@router.get("/my-subscribers", response_model=SubscriptionListResponse)
async def get_my_subscribers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of users subscribed to current user
    """
    try:
        subscriptions, total = SubscriptionService.get_user_subscribers(
            db=db,
            user_id=current_user.id,
            page=page,
            per_page=per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        # Add user info to each subscription
        subscription_responses = []
        for subscription in subscriptions:
            subscription_data = SubscriptionResponse.from_orm(subscription)
            subscription_data.owner_username = subscription.owner.signup_username
            subscription_data.subscriber_username = subscription.subscriber.signup_username
            subscription_responses.append(subscription_data)
        
        return SubscriptionListResponse(
            subscriptions=subscription_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get subscribers error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching subscribers"
        )