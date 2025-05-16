from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from ..dependencies import get_process_manager, get_current_active_user
from ...core.process.workflow_manager import WorkflowManager, ProcessInstance as CoreProcessInstance, ProcessState
from ..dependencies import User as PydanticUser # Pydantic user model

router = APIRouter()

class ProcessCreationRequest(BaseModel):
    template_id: str
    batch_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ProcessInstanceResponse(BaseModel):
    id: str
    template_id: str
    batch_id: Optional[str] = None
    state: str # ProcessState will be converted to string
    current_step_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    progress_percentage: Optional[float] = None # Added from core model

@router.post("/create", response_model=ProcessInstanceResponse, summary="Create a new process instance")
async def create_process(
    request: ProcessCreationRequest,
    current_user: PydanticUser = Depends(get_current_active_user),
    pm: WorkflowManager = Depends(get_process_manager)
):
    try:
        instance = await pm.create_process_instance(
            template_id=request.template_id,
            batch_id=request.batch_id,
            metadata=request.metadata
        )
        status = await pm.get_process_status(instance.id) # Fetch full status to respond
        return ProcessInstanceResponse(**status) # Map to response model
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) # e.g. template not found
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create process instance: {str(e)}")

@router.post("/{process_id}/start", summary="Start a process instance")
async def start_process(
    process_id: str,
    current_user: PydanticUser = Depends(get_current_active_user),
    pm: WorkflowManager = Depends(get_process_manager)
):
    try:
        await pm.start_process(process_id)
        return {"message": f"Process {process_id} started by {current_user.username}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{process_id}/status", response_model=ProcessInstanceResponse, summary="Get process instance status")
async def get_process_status(
    process_id: str, 
    pm: WorkflowManager = Depends(get_process_manager)
):
    try:
        status = await pm.get_process_status(process_id)
        return ProcessInstanceResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Add more endpoints: pause, resume, abort, list processes etc. 