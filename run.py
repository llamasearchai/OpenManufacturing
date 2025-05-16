#!/usr/bin/env python
"""
Run script for the OpenManufacturing platform.

This script starts the FastAPI server using uvicorn.
"""

import uvicorn
import os

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Run the server
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    ) 