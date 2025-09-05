from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class SubscriptionType(str, Enum):
    BASIC = "basic"
    PREMIUM = "premium"


class SubscriptionRequest(BaseModel):
    owner_user_id: UUID
    subscription_type: SubscriptionType = SubscriptionType.BASIC


class UnsubscribeRequest(BaseModel):
    owner_user_id: UUID


class SubscriptionResponse(BaseModel):
    id: UUID
    owner_user_id: UUID
    subscriber_user_id: UUID
    subscription_type: str
    is_active: bool
    subscribed_at: datetime
    expires_at: Optional[datetime] = None
    owner_username: Optional[str] = None  # Owner's display name
    subscriber_username: Optional[str] = None  # Subscriber's display name
    
    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    subscriptions: List[SubscriptionResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class SubscriptionStatusResponse(BaseModel):
    is_subscribed: bool
    subscription: Optional[SubscriptionResponse] = None