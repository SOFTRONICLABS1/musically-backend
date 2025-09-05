from sqlalchemy.orm import Session
from app.models.user import AdminUser
from app.schemas.admin import AdminCreateRequest, AdminUpdateRequest, AdminRole
from app.core.security import verify_password, get_password_hash
from typing import Optional, Tuple, List
from datetime import datetime
from uuid import UUID
import uuid


class AdminService:
    
    @staticmethod
    def authenticate_admin(db: Session, email: str, password: str) -> Optional[AdminUser]:
        """Authenticate admin user"""
        admin = db.query(AdminUser).filter(
            AdminUser.email == email,
            AdminUser.is_active == True
        ).first()
        
        if not admin:
            return None
            
        if not verify_password(password, admin.password_hash):
            return None
            
        # Update last login
        admin.last_login = datetime.utcnow()
        db.commit()
        
        return admin
    
    @staticmethod
    def create_admin(
        db: Session, 
        admin_data: AdminCreateRequest, 
        created_by_id: Optional[UUID] = None
    ) -> AdminUser:
        """Create a new admin user"""
        # Check if email already exists
        existing_admin = db.query(AdminUser).filter(AdminUser.email == admin_data.email).first()
        if existing_admin:
            raise ValueError("Email already registered")
        
        # Check if username already exists
        existing_username = db.query(AdminUser).filter(AdminUser.username == admin_data.username).first()
        if existing_username:
            raise ValueError("Username already taken")
        
        # Create admin user
        admin = AdminUser(
            email=admin_data.email,
            username=admin_data.username,
            password_hash=get_password_hash(admin_data.password),
            role=admin_data.role,
            permissions=admin_data.permissions,
            created_by=created_by_id
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        return admin
    
    @staticmethod
    def get_admin_by_id(db: Session, admin_id: UUID) -> Optional[AdminUser]:
        """Get admin by ID"""
        return db.query(AdminUser).filter(
            AdminUser.id == admin_id,
            AdminUser.is_active == True
        ).first()
    
    @staticmethod
    def get_admin_by_email(db: Session, email: str) -> Optional[AdminUser]:
        """Get admin by email"""
        return db.query(AdminUser).filter(
            AdminUser.email == email,
            AdminUser.is_active == True
        ).first()
    
    @staticmethod
    def get_all_admins(
        db: Session, 
        page: int = 1, 
        per_page: int = 20
    ) -> Tuple[List[AdminUser], int]:
        """Get all admin users with pagination"""
        query = db.query(AdminUser).filter(AdminUser.is_active == True)
        total = query.count()
        
        admins = query.offset((page - 1) * per_page).limit(per_page).all()
        return admins, total
    
    @staticmethod
    def update_admin(
        db: Session, 
        admin_id: UUID, 
        update_data: AdminUpdateRequest
    ) -> Optional[AdminUser]:
        """Update admin user"""
        admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
        if not admin:
            return None
        
        # Check email uniqueness if updating email
        if update_data.email and update_data.email != admin.email:
            existing_admin = db.query(AdminUser).filter(
                AdminUser.email == update_data.email,
                AdminUser.id != admin_id
            ).first()
            if existing_admin:
                raise ValueError("Email already exists")
        
        # Check username uniqueness if updating username
        if update_data.username and update_data.username != admin.username:
            existing_username = db.query(AdminUser).filter(
                AdminUser.username == update_data.username,
                AdminUser.id != admin_id
            ).first()
            if existing_username:
                raise ValueError("Username already exists")
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(admin, field, value)
        
        admin.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(admin)
        
        return admin
    
    @staticmethod
    def deactivate_admin(db: Session, admin_id: UUID) -> bool:
        """Deactivate admin user"""
        admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
        if not admin:
            return False
        
        admin.is_active = False
        admin.updated_at = datetime.utcnow()
        db.commit()
        
        return True
    
    @staticmethod
    def has_permission(admin: AdminUser, required_permission: str) -> bool:
        """Check if admin has specific permission"""
        # Super admin has all permissions
        if admin.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Check role-based permissions
        role_permissions = {
            AdminRole.CONTENT_MODERATOR: [
                "view_content", "edit_content", "delete_content", 
                "view_users", "moderate_users"
            ],
            AdminRole.USER_MANAGER: [
                "view_users", "edit_users", "delete_users", 
                "view_content"
            ],
            AdminRole.ANALYTICS_VIEWER: [
                "view_analytics", "view_users", "view_content"
            ]
        }
        
        role_perms = role_permissions.get(admin.role, [])
        
        # Check if permission is in role permissions or custom permissions
        if required_permission in role_perms:
            return True
        
        if admin.permissions and required_permission in admin.permissions:
            return True
        
        return False