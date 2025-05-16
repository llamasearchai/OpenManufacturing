"""
Process management package for OpenManufacturing platform.

This package contains classes for workflow and process management, calibration,
and other manufacturing process-related functionality.
"""

from .workflow_manager import (
    WorkflowManager,
    ProcessState,
    ProcessStep,
    ProcessInstance,
    WorkflowTemplate,
)
from .calibration import CalibrationProfile  # Assuming calibration.py already exists

__all__ = [
    "WorkflowManager",
    "ProcessState",
    "ProcessStep",
    "ProcessInstance",
    "WorkflowTemplate",
    "CalibrationProfile",
]
