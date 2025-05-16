#!/usr/bin/env python
"""
Run script for the OpenManufacturing platform.

This script starts the FastAPI server using uvicorn.
"""

import uvicorn
import os
import logging
from dotenv import load_dotenv

# Import the FastAPI app instance
# This assumes your FastAPI app is defined in openmanufacturing/api/main.py
from openmanufacturing.api.main import app

# Load environment variables from .env file
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    reload = os.getenv("UVICORN_RELOAD", "False").lower() == "true"
    workers = int(os.getenv("UVICORN_WORKERS", "1"))

    logger.info(f"Starting server on {host}:{port}")
    if reload:
        logger.info("Auto-reload enabled.")
    if workers > 1 and not reload:
        logger.info(f"Running with {workers} workers.")

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # Uvicorn reload mode works best with 1 worker
    )
