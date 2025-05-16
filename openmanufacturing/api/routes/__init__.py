"""
API routes for the OpenManufacturing platform.

This package defines all API endpoints, categorized by functionality.
"""

from . import alignment, auth, devices, process, workflow

__all__ = ["alignment", "auth", "devices", "process", "workflow"]
