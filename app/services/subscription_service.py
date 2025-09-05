from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.user import UserSubscription, User
from app.schemas.subscription import SubscriptionRequest, SubscriptionType
from typing import Optional, List, Tuple
from datetime import datetime
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class SubscriptionService:
    
    @staticmethod
    def subscribe_to_user(
        db: Session, 
        subscriber_id: UUID, 
        owner_id: UUID,
        subscription_type: SubscriptionType = SubscriptionType.BASIC
    ) -> UserSubscription:
        """Subscribe a user to another user"""
        
        # Check if users exist
        subscriber = db.query(User).filter(User.id == subscriber_id).first()
        owner = db.query(User).filter(User.id == owner_id).first()
        
        if not subscriber or not owner:
            raise ValueError("User not found")
        
        # Prevent self-subscription
        if subscriber_id == owner_id:
            raise ValueError("Cannot subscribe to yourself")
        
        # Check if subscription already exists
        existing_subscription = db.query(UserSubscription).filter(
            and_(
                UserSubscription.owner_user_id == owner_id,
                UserSubscription.subscriber_user_id == subscriber_id,
                UserSubscription.is_active == True
            )
        ).first()
        
        if existing_subscription:
            raise ValueError("Already subscribed to this user")
        
        # Create subscription
        subscription = UserSubscription(
            owner_user_id=owner_id,
            subscriber_user_id=subscriber_id,
            subscription_type=subscription_type,
            is_active=True,
            subscribed_at=datetime.utcnow()
        )
        
        db.add(subscription)
        
        # Update owner's subscriber count
        owner.total_subscribers += 1
        
        db.commit()
        db.refresh(subscription)
        
        return subscription
    
    @staticmethod
    def unsubscribe_from_user(
        db: Session, 
        subscriber_id: UUID, 
        owner_id: UUID
    ) -> bool:
        """Unsubscribe from a user"""
        
        subscription = db.query(UserSubscription).filter(
            and_(
                UserSubscription.owner_user_id == owner_id,
                UserSubscription.subscriber_user_id == subscriber_id,
                UserSubscription.is_active == True
            )
        ).first()
        
        if not subscription:
            return False
        
        # Deactivate subscription
        subscription.is_active = False
        subscription.updated_at = datetime.utcnow()
        
        # Update owner's subscriber count
        owner = db.query(User).filter(User.id == owner_id).first()
        if owner and owner.total_subscribers > 0:
            owner.total_subscribers -= 1
        
        db.commit()
        
        return True
    
    @staticmethod
    def get_subscription_status(
        db: Session,
        subscriber_id: UUID,
        owner_id: UUID
    ) -> Optional[UserSubscription]:
        """Check if user is subscribed to another user"""
        
        return db.query(UserSubscription).filter(
            and_(
                UserSubscription.owner_user_id == owner_id,
                UserSubscription.subscriber_user_id == subscriber_id,
                UserSubscription.is_active == True
            )
        ).first()
    
    @staticmethod
    def get_user_subscriptions(
        db: Session,
        user_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[UserSubscription], int]:
        """Get all subscriptions for a user (who they're subscribed to)"""
        
        query = db.query(UserSubscription).join(
            User, UserSubscription.owner_user_id == User.id
        ).filter(
            and_(
                UserSubscription.subscriber_user_id == user_id,
                UserSubscription.is_active == True
            )
        )
        
        total = query.count()
        subscriptions = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return subscriptions, total
    
    @staticmethod
    def get_user_subscribers(
        db: Session,
        user_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[UserSubscription], int]:
        """Get all subscribers of a user (who's subscribed to them)"""
        
        query = db.query(UserSubscription).join(
            User, UserSubscription.subscriber_user_id == User.id
        ).filter(
            and_(
                UserSubscription.owner_user_id == user_id,
                UserSubscription.is_active == True
            )
        )
        
        total = query.count()
        subscriptions = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return subscriptions, total