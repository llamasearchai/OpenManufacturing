import logging
import os
import time
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from openmanufacturing.api.routes import alignment, auth, devices, workflow
from openmanufacturing.core.database.db import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api")

# Store API version as a variable to use elsewhere
API_VERSION = "1.0.0"

# Create FastAPI app
app = FastAPI(
    title="OpenManufacturing API",
    description="API for optical packaging automation platform",
    version=API_VERSION,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    """Log request/response info"""
    start_time = time.time()

    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        # Log request details
        logger.info(
            f"{request.client.host}:{request.client.port} - "
            f'"{request.method} {request.url.path}" {response.status_code} '
            f"{process_time:.3f}s"
        )

        return response
    except Exception as e:
        # Log exception
        logger.exception(f"Request failed: {str(e)}")

        # Return error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


# Add application routes
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(alignment.router)
app.include_router(workflow.router)

@app.get("/api/health")
async def health_check():
    """API health check endpoint"""
    return {"status": "ok", "version": API_VERSION}


@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    logger.info("Starting OpenManufacturing API")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        # Continue anyway - the database might be up soon

    # Check external services
    try:
        # Check database connectivity
        from openmanufacturing.core.database.db import get_db_session

        async with get_db_session() as session:
            await session.execute("SELECT 1")
        logger.info("Database connection successful")

        # Check other services if needed
        # For example, check vision system, motion controllers, etc.
    except Exception as e:
        logger.warning(f"Service check failed: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    logger.info("Shutting down OpenManufacturing API")

    # Close connections, cleanup, etc.
    # For example, stop any running alignment processes
    from openmanufacturing.api.dependencies import get_alignment_service

    # alignment_service = get_alignment_service() # Variable not used
    get_alignment_service()  # Call the function if it has side effects or to ensure it's covered

    # Close any other resources
