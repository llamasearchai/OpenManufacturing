import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from ...core.alignment import AlignmentParameters, AlignmentService
from ...core.database.models import User
from ...core.process import WorkflowManager
from ..dependencies import get_alignment_service, get_current_active_user, get_process_manager

router = APIRouter(prefix="/api/alignment", tags=["alignment"])


class AlignmentRequest(BaseModel):
    """Request model for alignment operations"""

    device_id: str
    parameters: Optional[Dict[str, Any]] = None
    process_id: Optional[str] = None
    batch_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AlignmentResponse(BaseModel):
    """Response model for alignment operations"""

    request_id: str
    status: str
    process_id: Optional[str] = None
    message: Optional[str] = None


class AlignmentResult(BaseModel):
    """Detailed alignment result"""

    request_id: str
    device_id: str
    success: bool
    optical_power_dbm: float
    position: Dict[str, float]
    duration_ms: int
    iterations: int
    timestamp: str
    process_id: Optional[str] = None
    error: Optional[str] = None
    status: str


@router.post("/align", response_model=AlignmentResponse)
async def start_alignment(
    request: AlignmentRequest,
    background_tasks: BackgroundTasks,
    alignment_service: AlignmentService = Depends(get_alignment_service),
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user),
):
    """Start a new alignment operation"""
    request_id = str(uuid.uuid4())

    # Check if process_id is provided and valid
    process_id = request.process_id
    if process_id:
        try:
            process_status = await process_manager.get_process_status(process_id)
            if process_status["state"] not in ["PENDING", "RUNNING"]:
                raise HTTPException(
                    status_code=400, detail=f"Process {process_id} is not in a valid state"
                )
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Process {process_id} not found")

    # Convert request parameters to alignment parameters
    if request.parameters:
        try:
            params = AlignmentParameters(**request.parameters)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    else:
        params = AlignmentParameters()  # Use defaults

    # Add user info to metadata
    metadata = request.metadata or {}
    metadata["user_id"] = current_user.id
    metadata["username"] = current_user.username

    # Schedule alignment in background
    background_tasks.add_task(
        alignment_service.align_device,
        request_id=request_id,
        device_id=request.device_id,
        parameters=params,
        process_id=process_id,
        metadata=metadata,
    )

    return AlignmentResponse(
        request_id=request_id,
        status="scheduled",
        process_id=process_id,
        message="Alignment operation scheduled",
    )


@router.get("/status/{request_id}", response_model=Optional[AlignmentResult])
async def get_alignment_status(
    request_id: str,
    alignment_service: AlignmentService = Depends(get_alignment_service),
    current_user: User = Depends(get_current_active_user),
):
    """Get status of an alignment operation"""
    result = await alignment_service.get_alignment_status(request_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Alignment request {request_id} not found")
    return result


@router.get("/history/{device_id}", response_model=List[AlignmentResult])
async def get_alignment_history(
    device_id: str,
    limit: int = Query(10, ge=1, le=100),
    alignment_service: AlignmentService = Depends(get_alignment_service),
    current_user: User = Depends(get_current_active_user),
):
    """Get alignment history for a device"""
    history = alignment_service.get_alignment_history(device_id, limit)
    return history


@router.post("/cancel/{request_id}", response_model=AlignmentResponse)
async def cancel_alignment(
    request_id: str,
    alignment_service: AlignmentService = Depends(get_alignment_service),
    current_user: User = Depends(get_current_active_user),
):
    """Cancel an ongoing alignment operation"""
    success = alignment_service.cancel_alignment(request_id)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"Alignment request {request_id} not found or already completed"
        )

    return AlignmentResponse(
        request_id=request_id, status="cancelled", message="Alignment operation cancelled"
    )
