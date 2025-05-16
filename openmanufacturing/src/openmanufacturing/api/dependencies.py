from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # type: ignore
import os
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel, ValidationError

# Adjusted relative imports for the new structure
from ..core.database.db import get_session
from ..core.database.models import User as DBUser # Renamed to avoid conflict with Pydantic User model
from ..core.alignment.service import AlignmentService # Assuming this path is correct
from ..core.process.workflow_manager import WorkflowManager # Assuming this path is correct

# JWT configuration - ควรจะมาจาก config file หรือ environment variables
SECRET_KEY = os.environ.get("SECRET_KEY", "a_very_secret_key_for_development_only_345_!@%")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# OAuth2PasswordBearer takes tokenUrl relative to the app root
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token") # Adjusted from /api/auth/token to be relative to auth router

# --- Pydantic models for token data --- #
class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: list[str] = []

class User(BaseModel): # Pydantic model for User, distinct from SQLAlchemy model
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    scopes: list[str] = []

# --- Global service instances (initialized in api/main.py or similar central place) --- #
# These are set by set_alignment_service and set_process_manager
_alignment_service: Optional[AlignmentService] = None
_workflow_manager: Optional[WorkflowManager] = None

def set_alignment_service(service: AlignmentService) -> None:
    global _alignment_service
    _alignment_service = service

def get_alignment_service() -> AlignmentService:
    if _alignment_service is None:
        # This indicates a programming error: service not initialized before use.
        raise RuntimeError("Alignment service has not been initialized.")
    return _alignment_service

def set_process_manager(manager: WorkflowManager) -> None:
    global _workflow_manager
    _workflow_manager = manager

def get_process_manager() -> WorkflowManager:
    if _workflow_manager is None:
        # This indicates a programming error: service not initialized before use.
        raise RuntimeError("Workflow manager has not been initialized.")
    return _workflow_manager

# --- User and Authentication Dependencies --- #

async def get_user_from_db(username: str, session: AsyncSession) -> Optional[DBUser]:
    query = select(DBUser).where(DBUser.username == username)
    result = await session.execute(query)
    return result.scalars().first()

async def get_current_user_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials - Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(username=username, scopes=token_scopes)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception
    except ValidationError: # Pydantic validation error for TokenData
        raise credentials_exception
    return token_data

async def get_current_db_user(
    token_data: TokenData = Depends(get_current_user_token_data),
    session: AsyncSession = Depends(get_session)
) -> DBUser:
    user = await get_user_from_db(username=token_data.username, session=session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(
    current_user: DBUser = Depends(get_current_db_user),
    token_data: TokenData = Depends(get_current_user_token_data) # Get scopes from token
) -> User: # Returns Pydantic User model
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    # Construct Pydantic User model from DBUser and token scopes
    return User(
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        scopes=token_data.scopes # Use scopes from the token
    )

# --- Scope-based Access Control --- #
async def require_scope(
    security_scopes: SecurityScopes,
    current_user: User = Depends(get_current_active_user) # Uses Pydantic User with scopes
):
    if security_scopes.scopes: # If scopes are defined for the endpoint
        # current_user.scopes should be populated by get_current_active_user from the token
        user_scopes = set(current_user.scopes)
        required_scopes = set(security_scopes.scopes)
        
        if not required_scopes.issubset(user_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Requires scopes: {', '.join(required_scopes)}",
                headers={"WWW-Authenticate": security_scopes.scope_str},
            )
    # If no scopes are defined on the endpoint, access is granted (if authenticated)
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(require_scope) # Use Pydantic User from require_scope
) -> User:
    # Check if 'admin' scope is present or if user has an is_admin flag from DB (redundant if scopes are primary)
    # For simplicity, let's assume an 'admin' scope or an is_admin attribute on the Pydantic User model
    # The User model created in get_current_active_user gets is_admin from DBUser.
    if not current_user.is_admin: # Check the flag derived from DB
        # Alternatively, or in addition, check for an 'admin' scope:
        # if "admin" not in current_user.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required."
        )
    return current_user

# --- Token Creation Utility --- #
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 