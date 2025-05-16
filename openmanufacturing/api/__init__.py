"""
OpenManufacturing API package.

This package contains the FastAPI application, route definitions, and API dependencies.
"""

from . import dependencies, main, routes

__all__ = ["main", "dependencies", "routes"]
