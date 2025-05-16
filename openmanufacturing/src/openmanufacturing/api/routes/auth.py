from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from ..dependencies import get_session, create_access_token, get_current_active_user, User as PydanticUser, TokenData
from ...core.database.models import User as DBUser # SQLAlchemy model
from ...core.security import verify_password, get_password_hash # Assuming these exist in core.security

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    scopes: list[str]

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    is_admin: bool = False # Optional: admin creation should be restricted

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool

@router.post("/token", response_model=Token, summary="Login and get access token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    session: AsyncSession = Depends(get_session)
):
    user = await get_user_from_db(form_data.username, session)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Define user scopes (example: could be dynamic based on user roles/permissions)
    user_scopes = ["read:items", "write:items"]
    if user.is_admin:
        user_scopes.extend(["admin:access", "read:users", "write:users"])

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user_scopes},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "username": user.username,
        "scopes": user_scopes
    }

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Register a new user")
async def register_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    db_user = await get_user_from_db(user_in.username, session)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_password = get_password_hash(user_in.password)
    # In a real app, restrict is_admin creation or handle via a separate admin endpoint
    new_user = DBUser(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        is_active=True, # Activate user by default, or implement email verification
        is_admin=user_in.is_admin 
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return UserResponse(**new_user.__dict__)


@router.get("/me", response_model=PydanticUser, summary="Get current authenticated user details")
async def read_users_me(current_user: PydanticUser = Depends(get_current_active_user)):
    return current_user

# Helper function (should be in dependencies or a user service module)
from ..dependencies import ACCESS_TOKEN_EXPIRE_MINUTES # Re-import for clarity if used here
from pydantic import BaseModel # Added for Token model
from typing import Optional # Added for UserCreate model

async def get_user_from_db(username: str, session: AsyncSession) -> Optional[DBUser]:
    from sqlalchemy import select # type: ignore
    query = select(DBUser).where(DBUser.username == username)
    result = await session.execute(query)
    return result.scalars().first() 