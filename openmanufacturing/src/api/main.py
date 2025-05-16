from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import os
from typing import List, Dict, Any

from .routes import alignment, process, auth, devices, workflow
from ..core.database.db import init_db

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="OpenManufacturing API",
    description="API for the OpenManufacturing optical packaging and assembly platform",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(alignment.router)
app.include_router(process.router)
app.include_router(devices.router)
app.include_router(workflow.router)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to response"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "detail": str(exc)},
    )

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "version": app.version}

@app.get("/api/config")
async def get_public_config():
    """Get public configuration"""
    return {
        "version": app.version,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "features": {
            "alignment": True,
            "process_management": True,
            "inventory": True,
            "vision": True
        }
    }
