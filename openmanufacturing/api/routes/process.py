from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import uuid
from datetime import datetime
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..dependencies import get_process_manager, get_current_active_user, get_session
from ...core.process.workflow_manager import WorkflowManager, ProcessState
from ...core.database.models import User, WorkflowTemplate as DBWorkflowTemplate, ProcessInstance as DBProcessInstance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/process", tags=["process"])

class ProcessTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    steps: List[Dict[str, Any]]

class ProcessTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None

class ProcessTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: str
    steps: List[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: str

class ProcessInstanceRequest(BaseModel):
    template_id: str
    batch_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ProcessInstanceResponse(BaseModel):
    id: str
    template_id: str
    template_name: str
    batch_id: Optional[str] = None
    state: str
    current_step_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percentage: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    step_results: Optional[Dict[str, Any]] = None

@router.post("/templates", response_model=ProcessTemplateResponse, status_code=201)
async def create_process_template_endpoint(
    request: ProcessTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new process template (workflow template)."""
    query = select(DBWorkflowTemplate).where(DBWorkflowTemplate.name == request.name, DBWorkflowTemplate.version == request.version)
    existing_template = await session.scalar(query)
    if existing_template:
        raise HTTPException(
            status_code=409, 
            detail=f"Process template with name '{request.name}' and version '{request.version}' already exists."
        )
    new_template = DBWorkflowTemplate(
        id=str(uuid.uuid4()), name=request.name, description=request.description,
        version=request.version, steps=request.steps, created_by=current_user.id # User.id is int
    )
    session.add(new_template)
    await session.commit()
    await session.refresh(new_template)
    # Assuming User model has a username attribute for created_by string response
    return ProcessTemplateResponse(
        id=new_template.id, name=new_template.name, description=new_template.description,
        version=new_template.version, steps=new_template.steps, created_at=new_template.created_at,
        updated_at=new_template.updated_at, created_by=current_user.username
    )

@router.get("/templates", response_model=List[ProcessTemplateResponse])
async def list_process_templates_endpoint(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user) 
):
    """List all process templates (workflow templates)."""
    query = select(DBWorkflowTemplate).order_by(DBWorkflowTemplate.name).offset(skip).limit(limit)
    templates = (await session.execute(query)).scalars().all()
    response_templates = []
    for template in templates:
        creator_username = "system" # Default if no creator
        if template.created_by: # If created_by is not None
            # Efficiently get username if User model is related, otherwise fetch
            # Assuming DBWorkflowTemplate has a relationship 'creator' to User model
            if template.creator: 
                creator_username = template.creator.username
            else: # Fallback: Fetch user if relationship not eagerly loaded or defined
                creator_user = await session.get(User, template.created_by)
                if creator_user:
                    creator_username = creator_user.username
        response_templates.append(ProcessTemplateResponse(
            id=template.id, name=template.name, description=template.description,
            version=template.version, steps=template.steps, created_at=template.created_at,
            updated_at=template.updated_at, created_by=creator_username 
        ))
    return response_templates

@router.get("/templates/{template_id}", response_model=ProcessTemplateResponse)
async def get_process_template_endpoint(
    template_id: str, 
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific process template (workflow template)."""
    template = await session.get(DBWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Process template not found")
    creator_username = "system"
    if template.created_by:
        if template.creator: 
            creator_username = template.creator.username
        else: 
            creator_user = await session.get(User, template.created_by)
            if creator_user: 
                creator_username = creator_user.username
    return ProcessTemplateResponse(
        id=template.id, name=template.name, description=template.description,
        version=template.version, steps=template.steps, created_at=template.created_at,
        updated_at=template.updated_at, created_by=creator_username
    )

@router.put("/templates/{template_id}", response_model=ProcessTemplateResponse)
async def update_process_template_endpoint(
    template_id: str, 
    request: ProcessTemplateUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Update an existing process template."""
    template = await session.get(DBWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Process template not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    template.updated_at = datetime.now() # Explicitly set updated_at

    await session.commit()
    await session.refresh(template)

    creator_username = "system"
    if template.created_by:
        if template.creator:
            creator_username = template.creator.username
        else:
            user = await session.get(User, template.created_by)
            if user: 
                creator_username = user.username

    return ProcessTemplateResponse(
        id=template.id, name=template.name, description=template.description,
        version=template.version, steps=template.steps, created_at=template.created_at,
        updated_at=template.updated_at, created_by=creator_username
    )

@router.delete("/templates/{template_id}", status_code=204)
async def delete_process_template_endpoint(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # Consider admin only: get_current_admin_user
):
    """Delete a process template."""
    template = await session.get(DBWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Process template not found")
    
    # Check if template is used by any active process instances
    active_instances_query = select(DBProcessInstance).where(
        DBProcessInstance.template_id == template_id, 
        DBProcessInstance.state.in_([
            ProcessState.PENDING.name, 
            ProcessState.RUNNING.name, 
            ProcessState.PAUSED.name
        ])
    )
    active_instances_exist = await session.execute(active_instances_query)
    if active_instances_exist.scalars().first():
        raise HTTPException(status_code=400, detail="Cannot delete template: It is used by one or more active process instances.")

    await session.delete(template)
    await session.commit()
    return None # FastAPI handles 204 No Content response

@router.post("/instances", response_model=ProcessInstanceResponse, status_code=201)
async def create_process_instance_endpoint(
    request: ProcessInstanceRequest, 
    background_tasks: BackgroundTasks,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new process instance from a template and schedule it to start."""
    try:
        instance_metadata = request.metadata or {}
        instance_metadata["created_by_user_id"] = current_user.id
        instance_metadata["created_by_username"] = current_user.username
        
        # Ensure template exists before creating instance
        async with get_session() as session: # Use a new session for this check
            template_exists = await session.get(DBWorkflowTemplate, request.template_id)
            if not template_exists:
                raise ValueError(f"Template not found: {request.template_id}")

        instance = await process_manager.create_process_instance(
            template_id=request.template_id, 
            batch_id=request.batch_id, 
            metadata=instance_metadata
        )
        # The create_process_instance in WorkflowManager should set the initial state to PENDING
        # and save basic instance data to DB.
        
        # Schedule the actual start of the process in the background
        background_tasks.add_task(process_manager.start_process, instance.id)
        
        # Return the status of the PENDING instance
        # The get_process_status should reflect the initial PENDING state and metadata.
        status_after_creation = await process_manager.get_process_status(instance.id)
        return ProcessInstanceResponse(**status_after_creation) 

    except ValueError as e:
        if "Template not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "Batch not found" in str(e): # Assuming WorkflowManager might check batch validity
            raise HTTPException(status_code=404, detail=str(e))
        else:
            logger.warning(f"ValueError during process instance creation: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating process instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during process instance creation.")

@router.post("/instances/{process_id}/start", response_model=ProcessInstanceResponse)
async def start_process_instance_endpoint(
    process_id: str, 
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Explicitly start a PENDING process instance."""
    try:
        # WorkflowManager.start_process should handle checking current state (e.g., must be PENDING)
        # and then transition it to RUNNING and begin execution.
        await process_manager.start_process(process_id) # This should be an async operation that kicks off the process
        
        # Give a brief moment for the process state to potentially update if start_process is very fast
        # or if it involves background tasks that update state quickly.
        await asyncio.sleep(0.1) 
        
        status_after_start_request = await process_manager.get_process_status(process_id)
        if status_after_start_request["state"] not in [ProcessState.RUNNING.name, ProcessState.PENDING.name]:
             # If it's PENDING, it means the background task hasn't picked it up yet, which is okay.
             # If it's already RUNNING, that's also good.
             # If it's FAILED/COMPLETED immediately, that's an issue handled by get_process_status response.
             pass # No specific error here, client will see the state.

        return ProcessInstanceResponse(**status_after_start_request)

    except ValueError as e: # Typically if process_id not found, or invalid state transition by manager
        logger.warning(f"ValueError starting process {process_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) # 400 for bad request (e.g. already running/done)
                                                            # 404 if process_id itself is not found by get_process_status
    except HTTPException: # Re-raise if already an HTTPException
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting process {process_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error while starting process {process_id}.")

@router.get("/instances/{process_id}", response_model=ProcessInstanceResponse)
async def get_process_instance_status_endpoint(
    process_id: str, 
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user) # Auth consistency
):
    """Get status of a specific process instance."""
    try:
        status = await process_manager.get_process_status(process_id)
        # The WorkflowManager.get_process_status is expected to return a dict
        # that matches all fields required by ProcessInstanceResponse.
        return ProcessInstanceResponse(**status)
    except ValueError as e: # Raised by get_process_status if not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting status for process {process_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error getting process status for {process_id}.")

@router.get("/instances", response_model=List[ProcessInstanceResponse])
async def list_process_instances_endpoint(
    batch_id: Optional[str] = Query(None),
    template_id: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session), # Direct DB query for listing
    current_user: User = Depends(get_current_active_user)
):
    """List process instances with optional filtering and pagination."""
    try:
        query = select(DBProcessInstance).options(selectinload(DBProcessInstance.template)) # Eager load template for name
        if batch_id:
            query = query.where(DBProcessInstance.batch_id == batch_id)
        if template_id:
            query = query.where(DBProcessInstance.template_id == template_id)
        if state:
            query = query.where(DBProcessInstance.state == state)
        
        query = query.order_by(DBProcessInstance.created_at.desc()).offset(offset).limit(limit)
        db_instances = (await session.execute(query)).scalars().all()

        response_list = []
        for inst in db_instances:
            template_name = inst.template.name if inst.template else "N/A"
            # Progress percentage might need to be calculated or stored more reliably.
            # For now, assuming it might be in metadata or default to 0.
            # WorkflowManager.get_process_status is the source of truth for a single instance.
            # This list view might show a simplified or slightly stale progress from DB metadata.
            core_instance_data = {
                "id": inst.id,
                "template_id": inst.template_id,
                "template_name": template_name,
                "batch_id": inst.batch_id,
                "state": inst.state,
                "current_step_id": inst.current_step_id,
                "started_at": inst.started_at,
                "completed_at": inst.completed_at,
                "metadata": inst.metadata,
                "step_results": inst.step_results,
                "progress_percentage": 0.0 # Placeholder, needs calculation logic
            }
            if inst.metadata and "progress_percentage" in inst.metadata:
                core_instance_data["progress_percentage"] = inst.metadata["progress_percentage"]
            elif inst.state == ProcessState.COMPLETED.name:
                core_instance_data["progress_percentage"] = 100.0
            
            response_list.append(ProcessInstanceResponse(**core_instance_data))
        return response_list
    except Exception as e:
        logger.error(f"Error listing process instances: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while listing process instances.")

@router.post("/instances/{process_id}/pause", response_model=ProcessInstanceResponse)
async def pause_process_endpoint(
    process_id: str,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Pause a running process."""
    try:
        await process_manager.pause_process(process_id)
        status = await process_manager.get_process_status(process_id)
        return ProcessInstanceResponse(**status)
    except ValueError as e: # Process not found or invalid state for pause
        logger.warning(f"ValueError pausing process {process_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) 
    except Exception as e:
        logger.error(f"Error pausing process {process_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error pausing process {process_id}.")

@router.post("/instances/{process_id}/resume", response_model=ProcessInstanceResponse)
async def resume_process_endpoint(
    process_id: str,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Resume a paused process."""
    try:
        await process_manager.resume_process(process_id)
        status = await process_manager.get_process_status(process_id)
        return ProcessInstanceResponse(**status)
    except ValueError as e: # Process not found or invalid state for resume
        logger.warning(f"ValueError resuming process {process_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error resuming process {process_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error resuming process {process_id}.")

@router.post("/instances/{process_id}/abort", response_model=ProcessInstanceResponse)
async def abort_process_endpoint(
    process_id: str,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Abort a process."""
    try:
        await process_manager.abort_process(process_id)
        status = await process_manager.get_process_status(process_id)
        return ProcessInstanceResponse(**status)
    except ValueError as e: # Process not found or invalid state for abort
        logger.warning(f"ValueError aborting process {process_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error aborting process {process_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error aborting process {process_id}.")