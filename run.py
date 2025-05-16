#!/usr/bin/env python3
"""
OpenManufacturing platform startup script.

This script starts the OpenManufacturing API server.
"""

import argparse
import asyncio
import logging
import sys

import uvicorn


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="OpenManufacturing API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--log-level", type=str, default="info", help="Logging level")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")
    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse command-line arguments
    args = parse_args()

    # Configure logging
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger("openmanufacturing")
    logger.info(f"Starting OpenManufacturing API on {args.host}:{args.port}")

    # Start web server
    try:
        config = uvicorn.Config(
            app="openmanufacturing.api.main:app",
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower(),
            reload=args.reload
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
