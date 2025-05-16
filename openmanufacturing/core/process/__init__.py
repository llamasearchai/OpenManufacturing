"""
Process management package for OpenManufacturing platform.

This package contains classes for workflow and process management, calibration,
and other manufacturing process-related functionality.
"""

from .calibration import CalibrationProfile  # Assuming calibration.py already exists
from .workflow_manager import (
    ProcessInstance,
    ProcessState,
    ProcessStep,
    WorkflowManager,
    WorkflowTemplate,
)

__all__ = [
    "WorkflowManager",
    "ProcessState",
    "ProcessStep",
    "ProcessInstance",
    "WorkflowTemplate",
    "CalibrationProfile",
]
