"""
API routes for the OpenManufacturing platform.

This package defines all API endpoints, categorized by functionality.
"""

from . import alignment
from . import auth
from . import devices
from . import process
from . import workflow

__all__ = [
    "alignment",
    "auth",
    "devices",
    "process",
    "workflow"
]
