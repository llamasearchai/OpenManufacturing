import logging
import os
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from sqlalchemy import text

from .models import Base

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/openmfg")

# Create engine
engine: Optional[AsyncEngine] = None

def get_engine() -> AsyncEngine:
    """Get SQLAlchemy engine, creating it if necessary"""
    global engine
    if engine is None:
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            future=True,
            pool_size=5,
            max_overflow=10,
        )
    return engine

# Session factory
async_session_factory = None

def get_session_factory():
    """Get SQLAlchemy session factory"""
    global async_session_factory
    if async_session_factory is None:
        async_session_factory = sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return async_session_factory

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise
    finally:
        await session.close()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (used in FastAPI dependency injection)"""
    async with get_db_session() as session:
        yield session

async def init_db() -> None:
    """Initialize database schema"""
    try:
        # Create tables
        engine = get_engine()
        async with engine.begin() as conn:
            # Drop tables for development if environment variable is set
            if os.environ.get("DROP_TABLES") == "true":
                logger.warning("Dropping all tables! (DEVELOPMENT ONLY)")
                await conn.run_sync(Base.metadata.drop_all)
            
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
        
        # Create initial data if needed
        await create_initial_data()
        
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

async def create_initial_data() -> None:
    """Create initial database data"""
    from .models import User
    from passlib.context import CryptContext
    import hashlib
    
    # Only create initial data if admin user doesn't exist
    async with get_db_session() as session:
        # Check if admin user exists
        admin = await session.get(User, 1)
        
        if admin is None:
            # Create admin user
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash("admin")  # Default password, should be changed
            
            admin = User(
                username="admin",
                email="admin@example.com",
                full_name="System Administrator",
                hashed_password=hashed_password,
                is_active=True,
                is_admin=True
            )
            
            session.add(admin)
            await session.commit()
            logger.info("Created default admin user")