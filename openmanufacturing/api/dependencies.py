import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openmanufacturing.core.alignment.service import AlignmentService
from openmanufacturing.core.database.db import get_session
from openmanufacturing.core.database.models import User
from openmanufacturing.core.process.workflow_manager import WorkflowManager

# JWT configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "development_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Rate limiting configuration
MAX_FAILED_ATTEMPTS = 5
RATE_LIMIT_DURATION = 300  # seconds (5 minutes)

# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Global service instances (initialized in the main application)
_alignment_service: Optional[AlignmentService] = None
_workflow_manager: Optional[WorkflowManager] = None
_redis_client: Optional[Redis] = None

# Alias for get_session for backward compatibility
get_db = get_session


def set_alignment_service(service: AlignmentService) -> None:
    """Set the global alignment service instance"""
    global _alignment_service
    _alignment_service = service


def get_alignment_service() -> AlignmentService:
    """Get the global alignment service instance"""
    if _alignment_service is None:
        raise RuntimeError("Alignment service not initialized")
    return _alignment_service


def set_process_manager(manager: WorkflowManager) -> None:
    """Set the global workflow manager instance"""
    global _workflow_manager
    _workflow_manager = manager


def get_process_manager() -> WorkflowManager:
    """Get the global workflow manager instance"""
    if _workflow_manager is None:
        raise RuntimeError("Workflow manager not initialized")
    return _workflow_manager


def set_redis_client(client: Redis) -> None:
    """Set the global Redis client instance"""
    global _redis_client
    _redis_client = client


async def get_redis_client() -> Redis:
    """Get the global Redis client instance"""
    global _redis_client
    
    if _redis_client is None:
        # Lazily initialize Redis client if not already done
        _redis_client = Redis.from_url(REDIS_URL, decode_responses=False)
    
    return _redis_client


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)
) -> User:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    # Get user from database
    query = select(User).where(User.username == username)
    result = await session.execute(query)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current admin user"""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user
