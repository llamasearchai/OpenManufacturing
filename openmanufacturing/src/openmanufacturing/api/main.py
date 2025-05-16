from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import os
from typing import List, Dict, Any

# Adjusted relative imports for the new structure
from .routes import alignment, process, auth, devices, workflow # Assuming workflow route will be created
from ..core.database.db import init_db, get_session
from ..core.alignment.service import AlignmentService
from ..core.process.workflow_manager import WorkflowManager
from .dependencies import set_alignment_service, set_process_manager, get_current_active_user # Example dependency

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="OpenManufacturing API",
    description="API for the OpenManufacturing optical packaging and assembly platform",
    version="1.0.0",
    # Add root_path if deploying behind a reverse proxy with a path prefix
    # root_path=os.environ.get("ROOT_PATH", "") 
)

# Configure CORS
# In a production environment, you should restrict origins more carefully.
# Example: origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
origins = ["*"] # For development

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mock Services Initialization (Replace with actual service setup) ---
# This is a simplified setup. In a real app, services might be initialized
# and passed around more robustly, possibly using dependency injection frameworks
# or FastAPI's Depends system more extensively at the router level.

# Placeholder for actual service instances
# These would typically be initialized based on configuration.
mock_motion_controller = None # Replace with actual MotionController instance
mock_image_processor = None   # Replace with actual ImageProcessor instance
mock_calibration_profile = None # Replace with actual CalibrationProfile instance

def initialize_global_services():
    """
    Initialize and set global services.
    This is a simplified approach for demonstration.
    In a more complex app, consider FastAPI's dependency injection for managing service lifecycles.
    """
    global _alignment_service_instance, _workflow_manager_instance
    
    # These would be properly initialized instances
    # from ..core.hardware.motion_controller import MotionController
    # from ..core.vision.image_processing import ImageProcessor
    # from ..core.process.calibration import CalibrationProfile

    # For now, creating placeholder instances or None
    # mc = MotionController(simulation_mode=True) # Example
    # ip = ImageProcessor(simulation_mode=True)   # Example
    # cp = CalibrationProfile()                   # Example
    
    # alignment_service = AlignmentService(
    #     motion_controller=mc, 
    #     image_processor=ip, 
    #     calibration_profile=cp
    # )
    # workflow_manager = WorkflowManager()
    # workflow_manager.register_component("alignment", alignment_service) # Example registration
    
    # For the purpose of this example, we'll use placeholders
    # to avoid making this file too complex with full service initialization logic.
    # Assume these are initialized elsewhere or through a more robust mechanism.
    alignment_service = AlignmentService(motion_controller=None, image_processor=None, calibration_profile=None) # Mocked
    workflow_manager = WorkflowManager() # Mocked
    
    set_alignment_service(alignment_service)
    set_process_manager(workflow_manager)
    logger.info("Mock global services set.")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("OpenManufacturing API starting up...")
    try:
        # Initialize database
        await init_db() # This should create tables if they don't exist
        logger.info("Database initialized (or connection checked).")
        
        # Initialize services that need to be available globally via dependencies.py
        initialize_global_services()
        
        logger.info("API startup complete.")
    except Exception as e:
        logger.error(f"Error during API startup: {str(e)}", exc_info=True)
        # Depending on the severity, you might want to prevent the app from starting
        # For now, just logging the error.

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up application on shutdown"""
    logger.info("OpenManufacturing API shutting down...")
    # Add any cleanup tasks here, e.g., closing database connections if not handled by context managers
    # await close_db_connection() # Example
    logger.info("API shutdown complete.")

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to response"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f} sec"
    return response

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "http_exception"},
    )

@app.exception_handler(Exception)
async def global_generic_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unexpected errors"""
    logger.error(f"Unhandled exception for request {request.method} {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred.", "type": "unhandled_exception"},
    )

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(alignment.router, prefix="/api/alignment", tags=["Alignment"], dependencies=[Depends(get_current_active_user)])
app.include_router(process.router, prefix="/api/process", tags=["Process"], dependencies=[Depends(get_current_active_user)])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"], dependencies=[Depends(get_current_active_user)])
app.include_router(workflow.router, prefix="/api/workflow", tags=["Workflow Templates"], dependencies=[Depends(get_current_active_user)])


@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "version": app.version, "timestamp": time.time()}

@app.get("/api/config", tags=["System"])
async def get_public_config_api(): # Renamed to avoid conflict with any other 'get_public_config'
    """Get public configuration (example)"""
    return {
        "serviceName": app.title,
        "version": app.version,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "features": { # Example feature flags
            "alignment_module_active": True,
            "process_management_active": True,
            "real_time_monitoring": True,
        }
    }

# This is the main FastAPI app instance
# To run: uvicorn openmanufacturing.api.main:app --reload (from openmanufacturing/src directory or with appropriate PYTHONPATH) 