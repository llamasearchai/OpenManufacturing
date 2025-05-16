from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
import uuid
import asyncio
from datetime import datetime

# Corrected relative imports for the new package structure
from ..dependencies import get_alignment_service, get_process_manager, get_current_active_user, require_scope
from ...core.alignment.alignment_engine import AlignmentParameters # As per main.txt structure
from ...core.alignment.service import AlignmentService # As per main.txt structure
from ...core.process.workflow_manager import WorkflowManager # As per main.txt structure
from ..dependencies import User as PydanticUser # Pydantic user model from dependencies

router = APIRouter() # Prefix and tags will be set in api/main.py when including the router

# --- Pydantic Models for Alignment API --- #

class AlignmentParametersRequest(BaseModel):
    position_tolerance_um: Optional[float] = Field(0.1, description="Position tolerance in micrometers")
    angle_tolerance_deg: Optional[float] = Field(0.05, description="Angle tolerance in degrees")
    optical_power_threshold: Optional[float] = Field(-3.0, description="Optical power threshold in dBm")
    max_iterations: Optional[int] = Field(100, description="Maximum iterations for alignment algorithms")
    use_machine_learning: Optional[bool] = Field(True, description="Flag to use ML-enhanced alignment if available")
    # Add any other specific parameters your AlignmentParameters dataclass might take
    # e.g., search_strategy: Optional[str] = "hill_climbing"

class AlignmentRequest(BaseModel):
    device_id: str = Field(..., description="Identifier of the device to be aligned")
    parameters: Optional[AlignmentParametersRequest] = Field(None, description="Custom alignment parameters")
    process_id: Optional[str] = Field(None, description="Optional process ID if this alignment is part of a larger workflow")
    batch_id: Optional[str] = Field(None, description="Optional batch ID for tracking")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Any additional metadata for this alignment task")

class AlignmentResponse(BaseModel):
    request_id: str = Field(..., description="Unique ID for this alignment request")
    status: str = Field(..., description="Status of the alignment operation (e.g., scheduled, in_progress, completed, failed)")
    process_id: Optional[str] = None
    message: Optional[str] = None
    details_url: Optional[str] = None

class AlignmentPosition(BaseModel):
    x: float
    y: float
    z: float

class AlignmentResultData(BaseModel): # Corresponds to AlignmentResult in main.txt (FastAPI response model)
    request_id: str
    device_id: str
    success: bool
    optical_power_dbm: Optional[float] = None
    position: Optional[AlignmentPosition] = None # Updated to use AlignmentPosition model
    duration_ms: Optional[int] = None
    timestamp: datetime
    process_id: Optional[str] = None
    error: Optional[str] = None
    # Add other relevant fields from your service's result structure
    # e.g., alignment_phase: Optional[str] = None
    # trajectory_points: Optional[int] = None

# --- API Endpoints --- #

@router.post("/start", 
             response_model=AlignmentResponse, 
             summary="Start a new alignment operation",
             dependencies=[Depends(require_scope)]) # Example of scope dependency
async def start_alignment(
    request_data: AlignmentRequest,
    background_tasks: BackgroundTasks,
    current_user: PydanticUser = Depends(get_current_active_user),
    alignment_service: AlignmentService = Depends(get_alignment_service),
    process_manager: WorkflowManager = Depends(get_process_manager) # Assuming process_manager might be needed
):
    """Initiates an alignment process for a specified device."""
    request_id = str(uuid.uuid4())
    
    # Validate process_id if provided
    if request_data.process_id:
        try:
            # This assumes process_manager.get_process_status exists and works as in main.txt example
            process_status = await process_manager.get_process_status(request_data.process_id)
            if process_status["state"] not in ["RUNNING", "PENDING"]: # Or relevant states
                raise HTTPException(status_code=400, detail=f"Process {request_data.process_id} is not in a valid state for new tasks.")
        except ValueError: # Assuming this is raised if process_id not found
            raise HTTPException(status_code=404, detail=f"Process {request_data.process_id} not found.")

    # Convert request parameters to the core AlignmentParameters dataclass
    core_params_dict = {}
    if request_data.parameters:
        core_params_dict = request_data.parameters.model_dump(exclude_unset=True)
    
    try:
        # Assuming AlignmentParameters can be instantiated from a dict
        core_alignment_params = AlignmentParameters(**core_params_dict)
    except Exception as e: # Catch potential errors from dataclass instantiation
        raise HTTPException(status_code=400, detail=f"Invalid alignment parameters: {str(e)}")

    # Schedule the alignment task to run in the background
    # The alignment_service.align_device method should be an async function
    background_tasks.add_task(
        alignment_service.align_device, # Ensure this method exists and matches signature
        request_id=request_id,
        device_id=request_data.device_id,
        parameters=core_alignment_params, # Pass the dataclass instance
        process_id=request_data.process_id,
        batch_id=request_data.batch_id, # Assuming align_device accepts batch_id
        metadata=request_data.metadata   # Assuming align_device accepts metadata
    )
    
    # Construct details URL (example)
    # details_url = f"/api/alignment/status/{request_id}" # Relative to API root
    
    return AlignmentResponse(
        request_id=request_id,
        status="Alignment operation scheduled successfully.",
        process_id=request_data.process_id,
        message=f"Alignment for device {request_data.device_id} has been scheduled by {current_user.username}.",
        # details_url=details_url
    )

@router.get("/status/{alignment_request_id}", 
            response_model=AlignmentResultData, 
            summary="Get status and result of an alignment operation")
async def get_alignment_status(
    alignment_request_id: str,
    alignment_service: AlignmentService = Depends(get_alignment_service)
):
    """Retrieves the current status or final result of a specific alignment operation."""
    result = await alignment_service.get_alignment_result(alignment_request_id) # Ensure this method exists
    if not result:
        raise HTTPException(status_code=404, detail=f"Alignment request {alignment_request_id} not found or result not yet available.")
    
    # Assuming result is a dict or object that can be mapped to AlignmentResultData
    # If result is already a Pydantic model compatible with AlignmentResultData, direct return is fine.
    # Otherwise, map fields carefully.
    # Example mapping if result is a dictionary:
    # return AlignmentResultData(**result) 
    # For this example, assuming get_alignment_result returns a Pydantic model or a compatible dict:
    return result

@router.get("/history/{device_id}", 
            response_model=List[AlignmentResultData], 
            summary="Get alignment history for a device")
async def get_alignment_history(
    device_id: str,
    limit: int = Query(10, ge=1, le=100, description="Number of history records to retrieve"),
    alignment_service: AlignmentService = Depends(get_alignment_service)
):
    """Fetches the alignment history for a given device ID."""
    history = await alignment_service.get_alignment_history(device_id, limit) # Ensure this method exists
    if not history:
        # Return empty list if no history, or 404 if device_id itself is invalid (service dependent)
        return [] 
    return history

@router.post("/cancel/{alignment_request_id}", 
             response_model=AlignmentResponse, 
             summary="Cancel an ongoing alignment operation")
async def cancel_alignment(
    alignment_request_id: str,
    alignment_service: AlignmentService = Depends(get_alignment_service)
):
    """Attempts to cancel an alignment operation that is currently in progress."""
    try:
        success = await alignment_service.cancel_alignment(alignment_request_id) # Ensure this method exists
        if not success:
            # This could mean it was not found, already completed, or not cancellable
            # The service should provide more context if possible, or raise specific exceptions
            raise HTTPException(status_code=404, detail=f"Alignment request {alignment_request_id} not found, already completed, or cannot be cancelled.")
    except Exception as e: # More specific exceptions from service are better
        raise HTTPException(status_code=500, detail=f"Error cancelling alignment: {str(e)}")

    return AlignmentResponse(
        request_id=alignment_request_id,
        status="Cancellation request processed.",
        message=f"Attempted to cancel alignment {alignment_request_id}. Check status for confirmation."
    ) 