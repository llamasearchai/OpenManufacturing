from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import logging

logger = logging.getLogger(__name__)

# SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://user:password@host:port/database"
# Prioritize environment variable, then a default for local development.
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/openmfg_test_db"
)
# Ensure the test DB name is different from production if this file is shared.
# For production, always use env var.

if "localhost" in SQLALCHEMY_DATABASE_URL or "127.0.0.1" in SQLALCHEMY_DATABASE_URL:
    logger.warning(f"Using local database URL: {SQLALCHEMY_DATABASE_URL}")

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=os.environ.get("SQLALCHEMY_ECHO", "False") == "True", future=True)

#expire_on_commit=False is useful for FastAPI so that attributes of an object
#are still available after the session is committed and closed.
AsyncSessionFactory = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_session() -> AsyncSession:
    """Dependency to get an AsyncSession."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initializes the database and creates tables if they don't exist."""
    async with engine.begin() as conn:
        logger.info("Initializing database: dropping and creating all tables (DEBUG MODE BEHAVIOR - remove for prod).")
        # In a real application, you would use Alembic for migrations instead of dropping/creating all.
        # For development and testing, this can be acceptable.
        # await conn.run_sync(Base.metadata.drop_all) # Be careful with this in any shared environment
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables checked/created.")

async def close_db_connection():
    logger.info("Closing database engine connection.")
    await engine.dispose() 