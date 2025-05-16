from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from typing import Optional, List, Dict, Any
import uuid
import secrets
import logging
from email.message import EmailMessage
import aiosmtplib
import re
import time
from redis.asyncio import Redis

from ..dependencies import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_active_user, get_current_admin_user, get_redis_client
from ...core.database.db import get_session
from ...core.database.models import User, PasswordReset

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Rate limiting constants
RATE_LIMIT_DURATION = 60  # seconds
MAX_FAILED_ATTEMPTS = 5

# Password strength regex
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$")

# Pydantic models
class Token(BaseModel):
    """Enhanced token response model"""
    access_token: str
    token_type: str
    username: str
    expires_at: datetime
    scopes: List[str]
    refresh_token: Optional[str] = None

class TokenData(BaseModel):
    """Token data model"""
    username: Optional[str] = None
    scopes: List[str] = []
    exp: Optional[datetime] = None

class UserRegister(BaseModel):
    """User registration model"""
    username: str = Field(..., min_length=4, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    
    @validator('password')
    def password_strength(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain: "
                "uppercase letter, lowercase letter, number, and special character"
            )
        return v
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must contain only letters, numbers, underscores, and hyphens')
        return v

class UserUpdate(BaseModel):
    """User update model"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserResponse(BaseModel):
    """User response model"""
    username: str
    email: str
    full_name: Optional[str] = None
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class UserInfo(BaseModel):
    """User information response model"""
    username: str
    email: str
    full_name: Optional[str] = None
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    scopes: List[str] = []

class PasswordResetRequest(BaseModel):
    """Password reset request model"""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model"""
    token: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_strength(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain: "
                "uppercase letter, lowercase letter, number, and special character"
            )
        return v

class ChangePasswordRequest(BaseModel):
    """Change password request model"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_strength(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain: "
                "uppercase letter, lowercase letter, number, and special character"
            )
        return v

# Helper functions
def verify_password(plain_password, hashed_password):
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Hash password"""
    return pwd_context.hash(password)

async def authenticate_user(session: AsyncSession, username: str, password: str):
    """Authenticate user with username and password"""
    query = select(User).where(User.username == username)
    result = await session.execute(query)
    user = result.scalars().first()
    
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire

def create_refresh_token(username: str):
    """Create refresh token"""
    refresh_token = secrets.token_urlsafe(64)
    return refresh_token

def generate_user_scopes(user: User) -> List[str]:
    """Generate a list of scopes based on user attributes"""
    scopes = ["read:own_user"]
    
    if user.is_admin:
        scopes.extend([
            "read:users", "create:users", "update:users", "delete:users",
            "create:templates", "delete:templates"
        ])
    
    # Add basic scopes for all active users
    if user.is_active:
        scopes.extend([
            "process:read", "process:create", "process:update",
            "device:read", "alignment:read", "alignment:create"
        ])
    
    return scopes

async def send_password_reset_email(email: str, token: str, background_tasks: BackgroundTasks):
    """Send password reset email"""
    # This would be configured to use an actual SMTP server
    # For demo purposes, we'll just log it
    
    reset_url = f"https://app.openmanufacturing.org/reset-password?token={token}"
    
    message = EmailMessage()
    message["From"] = "noreply@openmanufacturing.org"
    message["To"] = email
    message["Subject"] = "Password Reset Request"
    message.set_content(
        f"""
        Hello,
        
        You requested a password reset for your OpenManufacturing account.
        Please use the following link to reset your password:
        
        {reset_url}
        
        This link will expire in 24 hours.
        
        If you did not request this, please ignore this email.
        
        Regards,
        The OpenManufacturing Team
        """
    )
    
    # In production, you would send the email through an actual SMTP server
    # For now, we'll just log it
    async def send_email_task():
        try:
            logger.info(f"Would send password reset email to {email} with token {token}")
            # Uncomment in production
            # await aiosmtplib.send(message, hostname="smtp.example.com", port=587, use_tls=True)
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
    
    background_tasks.add_task(send_email_task)

async def check_rate_limit(request: Request, key_prefix: str, redis: Redis) -> bool:
    """Check if the request is within rate limits"""
    client_ip = request.client.host
    key = f"{key_prefix}:{client_ip}"
    
    # Get current count
    count = await redis.get(key)
    if count is None:
        # First attempt, set expiry
        await redis.set(key, 1, ex=RATE_LIMIT_DURATION)
        return True
    
    count = int(count)
    if count >= MAX_FAILED_ATTEMPTS:
        return False
    
    # Increment count
    await redis.incr(key)
    return True

async def reset_rate_limit(request: Request, key_prefix: str, redis: Redis):
    """Reset rate limit counter on successful authentication"""
    client_ip = request.client.host
    key = f"{key_prefix}:{client_ip}"
    await redis.delete(key)

# Routes
@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis_client)
):
    """Login endpoint to get access token with username and scopes"""
    # Check rate limiting
    rate_limit_key = "auth:login:failed"
    if not await check_rate_limit(request, rate_limit_key, redis):
        logger.warning(f"Rate limit exceeded for IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )
    
    # Authenticate user
    try:
        user = await authenticate_user(session, form_data.username, form_data.password)
        
        if not user:
            logger.warning(f"Failed login attempt for username: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            logger.warning(f"Login attempt for inactive user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Reset rate limit on successful login
        await reset_rate_limit(request, rate_limit_key, redis)
        
        # Generate user scopes
        scopes = generate_user_scopes(user)
        
        # Update last login timestamp
        user.last_login = datetime.utcnow()
        await session.commit()
        
        # Create access token with scopes
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token, expires_at = create_access_token(
            data={"sub": user.username, "scopes": scopes},
            expires_delta=access_token_expires
        )
        
        # Generate refresh token (optional)
        refresh_token = create_refresh_token(user.username)
        
        # Store refresh token in Redis with expiry (30 days)
        refresh_expires = 30 * 24 * 60 * 60  # 30 days in seconds
        await redis.set(f"refresh:{refresh_token}", user.username, ex=refresh_expires)
        
        logger.info(f"User {user.username} logged in successfully")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "expires_at": expires_at,
            "scopes": scopes,
            "refresh_token": refresh_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication",
        )

@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: str,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis_client)
):
    """Refresh access token using refresh token"""
    try:
        # Get username from refresh token
        username = await redis.get(f"refresh:{refresh_token}")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        username = username.decode('utf-8')
        
        # Get user from database
        query = select(User).where(User.username == username)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if not user or not user.is_active:
            # Delete the refresh token if user doesn't exist or is inactive
            await redis.delete(f"refresh:{refresh_token}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is inactive or does not exist",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate user scopes
        scopes = generate_user_scopes(user)
        
        # Create new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token, expires_at = create_access_token(
            data={"sub": user.username, "scopes": scopes},
            expires_delta=access_token_expires
        )
        
        # Generate new refresh token
        new_refresh_token = create_refresh_token(user.username)
        
        # Store new refresh token and delete old one
        refresh_expires = 30 * 24 * 60 * 60  # 30 days in seconds
        await redis.set(f"refresh:{new_refresh_token}", user.username, ex=refresh_expires)
        await redis.delete(f"refresh:{refresh_token}")
        
        logger.info(f"Access token refreshed for user {user.username}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "expires_at": expires_at,
            "scopes": scopes,
            "refresh_token": new_refresh_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh",
        )

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    session: AsyncSession = Depends(get_session)
):
    """Register a new user"""
    try:
        # Check if username already exists
        query = select(User).where(User.username == user_data.username)
        result = await session.execute(query)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        
        # Check if email already exists
        query = select(User).where(User.email == user_data.email)
        result = await session.execute(query)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True,  # Default to active
            is_admin=False,  # Default to non-admin
            created_at=datetime.utcnow()
        )
        
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        logger.info(f"New user registered: {new_user.username}")
        
        return UserResponse(
            username=new_user.username,
            email=new_user.email,
            full_name=new_user.full_name,
            is_admin=new_user.is_admin,
            is_active=new_user.is_active,
            created_at=new_user.created_at,
            last_login=new_user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration",
        )

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Request password reset"""
    try:
        # Find user by email
        query = select(User).where(User.email == request.email)
        result = await session.execute(query)
        user = result.scalars().first()
        
        # Always return 202 even if user not found (security best practice)
        if not user:
            logger.info(f"Password reset requested for non-existent email: {request.email}")
            return {"detail": "If the email is registered, you will receive a password reset link."}
        
        # Generate token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Store token in database
        reset_request = PasswordReset(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            is_used=False
        )
        session.add(reset_request)
        await session.commit()
        
        # Send email with token
        await send_password_reset_email(user.email, token, background_tasks)
        
        logger.info(f"Password reset requested for user: {user.username}")
        
        return {"detail": "If the email is registered, you will receive a password reset link."}
        
    except Exception as e:
        logger.error(f"Error during password reset request: {str(e)}")
        await session.rollback()
        # Still return success for security reasons
        return {"detail": "If the email is registered, you will receive a password reset link."}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: PasswordResetConfirm,
    session: AsyncSession = Depends(get_session)
):
    """Reset password with token"""
    try:
        # Find token in database
        query = select(PasswordReset).where(
            PasswordReset.token == request.token,
            PasswordReset.is_used == False,
            PasswordReset.expires_at > datetime.utcnow()
        )
        result = await session.execute(query)
        reset_request = result.scalars().first()
        
        if not reset_request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token",
            )
        
        # Get user
        user = await session.get(User, reset_request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found",
            )
        
        # Update password
        user.hashed_password = get_password_hash(request.new_password)
        
        # Mark token as used
        reset_request.is_used = True
        reset_request.used_at = datetime.utcnow()
        
        await session.commit()
        
        logger.info(f"Password reset successful for user: {user.username}")
        
        return {"detail": "Password reset successful"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during password reset: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during password reset",
        )

@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Change user's password"""
    try:
        # Verify current password
        if not verify_password(request.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        
        # Check that new password is different
        if request.current_password == request.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password",
            )
        
        # Update password
        current_user.hashed_password = get_password_hash(request.new_password)
        await session.commit()
        
        logger.info(f"Password changed for user: {current_user.username}")
        
        return {"detail": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during password change: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during password change",
        )

@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information with scopes"""
    try:
        # Generate user scopes
        scopes = generate_user_scopes(current_user)
        
        return UserInfo(
            username=current_user.username,
            email=current_user.email,
            full_name=current_user.full_name,
            is_admin=current_user.is_admin,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
            last_login=current_user.last_login,
            scopes=scopes
        )
    except Exception as e:
        logger.error(f"Error retrieving user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving user information",
        )

@router.put("/me", response_model=UserInfo)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Update current user information"""
    try:
        # Only allow updating certain fields for own user
        if user_data.email is not None:
            # Check if email is already used
            query = select(User).where(
                User.email == user_data.email,
                User.id != current_user.id
            )
            result = await session.execute(query)
            if result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
            current_user.email = user_data.email
            
        if user_data.full_name is not None:
            current_user.full_name = user_data.full_name
            
        # Don't allow regular users to change is_active or is_admin
        
        await session.commit()
        await session.refresh(current_user)
        
        # Generate user scopes
        scopes = generate_user_scopes(current_user)
        
        logger.info(f"User updated: {current_user.username}")
        
        return UserInfo(
            username=current_user.username,
            email=current_user.email,
            full_name=current_user.full_name,
            is_admin=current_user.is_admin,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
            last_login=current_user.last_login,
            scopes=scopes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error updating user",
        )

@router.post("/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_account(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis_client)
):
    """Deactivate user's own account"""
    try:
        current_user.is_active = False
        await session.commit()
        
        # Invalidate all refresh tokens for this user
        # This is a simplified approach - production might need a more efficient way to handle this
        # such as a separate invalidation list
        keys = await redis.keys(f"refresh:*")
        for key in keys:
            username = await redis.get(key)
            if username and username.decode('utf-8') == current_user.username:
                await redis.delete(key)
        
        logger.info(f"User deactivated: {current_user.username}")
        
        return {"detail": "Account deactivated successfully"}
        
    except Exception as e:
        logger.error(f"Error deactivating account: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error deactivating account",
        )

# Admin routes
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    admin_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_session)
):
    """List all users (admin only)"""
    try:
        query = select(User).offset(skip).limit(limit)
        result = await session.execute(query)
        users = result.scalars().all()
        
        return [
            UserResponse(
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_admin=user.is_admin,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login
            )
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error listing users",
        )

@router.get("/users/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    admin_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_session)
):
    """Get user details (admin only)"""
    try:
        query = select(User).where(User.username == username)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
            
        return UserResponse(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving user",
        )

@router.put("/users/{username}", response_model=UserResponse)
async def update_user(
    username: str,
    user_data: UserUpdate,
    admin_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_session)
):
    """Update user details (admin only)"""
    try:
        query = select(User).where(User.username == username)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
            
        # Update user fields
        if user_data.email is not None:
            # Check if email is already used
            email_query = select(User).where(
                User.email == user_data.email,
                User.id != user.id
            )
            email_result = await session.execute(email_query)
            if email_result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
            user.email = user_data.email
            
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
            
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
            
        if user_data.is_admin is not None:
            user.is_admin = user_data.is_admin
            
        await session.commit()
        await session.refresh(user)
        
        logger.info(f"User {username} updated by admin {admin_user.username}")
        
        return UserResponse(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error updating user",
        )

@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    admin_user: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis_client)
):
    """Delete user (admin only)"""
    try:
        if username == admin_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )
            
        query = select(User).where(User.username == username)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
            
        # Delete user
        await session.delete(user)
        await session.commit()
        
        # Invalidate all refresh tokens for this user
        keys = await redis.keys(f"refresh:*")
        for key in keys:
            stored_username = await redis.get(key)
            if stored_username and stored_username.decode('utf-8') == username:
                await redis.delete(key)
        
        logger.info(f"User {username} deleted by admin {admin_user.username}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error deleting user",
        )