from fastapi import APIRouter, Depends, HTTPException, Response, status, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import uuid
from datetime import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_process_manager, get_current_active_user, get_session
from core.process.workflow_manager import WorkflowManager, ProcessState
from core.database.models import User, WorkflowTemplate as DBWorkflowTemplate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["workflow"])

class WorkflowStepModel(BaseModel):
    id: str
    type: str
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = {}
    dependencies: List[str] = []
    timeout_seconds: Optional[int] = None
    retry_config: Optional[Dict[str, Any]] = None

class WorkflowModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: str
    steps: List[WorkflowStepModel]
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: str

class WorkflowCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    steps: List[Dict[str, Any]]

class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None

class WorkflowRunRequest(BaseModel):
    template_id: str
    parameters: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    current_step: Optional[str] = None
    parameters: Dict[str, Any] = {}
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str

@router.post("/templates", response_model=WorkflowModel, status_code=201)
async def create_workflow_template(
    request: WorkflowCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new workflow template"""
    # Check if template with same name and version exists
    query = select(DBWorkflowTemplate).where(
        DBWorkflowTemplate.name == request.name,
        DBWorkflowTemplate.version == request.version
    )
    existing = await session.execute(query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Workflow template with name '{request.name}' and version '{request.version}' already exists"
        )

    # Create new template
    template_id = str(uuid.uuid4())
    new_template = DBWorkflowTemplate(
        id=template_id,
        name=request.name,
        description=request.description,
        version=request.version,
        steps=request.steps,
        created_by=current_user.id
    )
    
    session.add(new_template)
    await session.commit()
    await session.refresh(new_template)
    
    # Convert steps to WorkflowStepModel objects
    steps = []
    for step in new_template.steps:
        steps.append(WorkflowStepModel(**step))
    
    return WorkflowModel(
        id=new_template.id,
        name=new_template.name,
        description=new_template.description,
        version=new_template.version,
        steps=steps,
        created_at=new_template.created_at,
        updated_at=new_template.updated_at,
        created_by=current_user.username
    )

@router.get("/templates", response_model=List[WorkflowModel])
async def list_workflow_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """List all workflow templates"""
    query = select(DBWorkflowTemplate).order_by(
        DBWorkflowTemplate.name, 
        DBWorkflowTemplate.version
    ).offset(skip).limit(limit)
    
    result = await session.execute(query)
    templates = result.scalars().all()
    
    response = []
    for template in templates:
        # Fetch creator's username if available
        creator_username = "system"
        if template.created_by:
            creator = await session.get(User, template.created_by)
            if creator:
                creator_username = creator.username
        
        # Convert steps to WorkflowStepModel objects
        steps = []
        for step in template.steps:
            steps.append(WorkflowStepModel(**step))
        
        response.append(WorkflowModel(
            id=template.id,
            name=template.name,
            description=template.description,
            version=template.version,
            steps=steps,
            created_at=template.created_at,
            updated_at=template.updated_at,
            created_by=creator_username
        ))
    
    return response

@router.get("/templates/{template_id}", response_model=WorkflowModel)
async def get_workflow_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific workflow template by ID"""
    template = await session.get(DBWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    # Fetch creator's username
    creator_username = "system"
    if template.created_by:
        creator = await session.get(User, template.created_by)
        if creator:
            creator_username = creator.username
    
    # Convert steps to WorkflowStepModel objects
    steps = []
    for step in template.steps:
        steps.append(WorkflowStepModel(**step))
    
    return WorkflowModel(
        id=template.id,
        name=template.name,
        description=template.description,
        version=template.version,
        steps=steps,
        created_at=template.created_at,
        updated_at=template.updated_at,
        created_by=creator_username
    )

@router.put("/templates/{template_id}", response_model=WorkflowModel)
async def update_workflow_template(
    template_id: str,
    request: WorkflowUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Update a workflow template"""
    template = await session.get(DBWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    # Check for name and version conflicts if updating those fields
    if request.name or request.version:
        query = select(DBWorkflowTemplate).where(
            DBWorkflowTemplate.id != template_id,
            DBWorkflowTemplate.name == (request.name or template.name),
            DBWorkflowTemplate.version == (request.version or template.version)
        )
        existing = await session.execute(query)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Another workflow template with the same name and version already exists"
            )
    
    # Update fields if provided
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    
    template.updated_at = datetime.now()
    
    await session.commit()
    await session.refresh(template)
    
    # Fetch creator's username
    creator_username = "system"
    if template.created_by:
        creator = await session.get(User, template.created_by)
        if creator:
            creator_username = creator.username
    
    # Convert steps to WorkflowStepModel objects
    steps = []
    for step in template.steps:
        steps.append(WorkflowStepModel(**step))
    
    return WorkflowModel(
        id=template.id,
        name=template.name,
        description=template.description,
        version=template.version,
        steps=steps,
        created_at=template.created_at,
        updated_at=template.updated_at,
        created_by=creator_username
    )

@router.delete("/templates/{template_id}", status_code=204)
async def delete_workflow_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a workflow template"""
    template = await session.get(DBWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    # TODO: Add check for active workflows using this template
    
    await session.delete(template)
    await session.commit()
    return None

@router.post("/execute", response_model=WorkflowExecutionResponse, status_code=201)
async def execute_workflow(
    request: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Execute a workflow template"""
    # Verify template exists
    template = await session.get(DBWorkflowTemplate, request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    # Prepare metadata
    metadata = request.metadata or {}
    metadata["created_by_user_id"] = current_user.id
    metadata["created_by_username"] = current_user.username
    
    try:
        # Create process instance
        instance = await process_manager.create_process_instance(
            template_id=request.template_id,
            metadata=metadata
        )
        
        # Start process in background
        background_tasks.add_task(process_manager.start_process, instance.id)
        
        # Get initial status
        status = await process_manager.get_process_status(instance.id)
        
        return WorkflowExecutionResponse(
            id=status["id"],
            workflow_id=status["template_id"],
            workflow_name=status["template_name"],
            status=status["state"],
            current_step=status["current_step_id"],
            parameters=request.parameters or {},
            results=status.get("step_results", {}),
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at"),
            created_by=current_user.username
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution_status(
    execution_id: str,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Get the status of a workflow execution"""
    try:
        status = await process_manager.get_process_status(execution_id)
        return WorkflowExecutionResponse(
            id=status["id"],
            workflow_id=status["template_id"],
            workflow_name=status["template_name"],
            status=status["state"],
            current_step=status["current_step_id"],
            parameters={},  # Parameters not stored in status
            results=status.get("step_results", {}),
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at"),
            created_by=status.get("metadata", {}).get("created_by_username", "system")
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting workflow execution status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/executions/{execution_id}/cancel", response_model=WorkflowExecutionResponse)
async def cancel_workflow_execution(
    execution_id: str,
    process_manager: WorkflowManager = Depends(get_process_manager),
    current_user: User = Depends(get_current_active_user)
):
    """Cancel a running workflow execution"""
    try:
        await process_manager.abort_process(execution_id)
        status = await process_manager.get_process_status(execution_id)
        
        return WorkflowExecutionResponse(
            id=status["id"],
            workflow_id=status["template_id"],
            workflow_name=status["template_name"],
            status=status["state"],
            current_step=status["current_step_id"],
            parameters={},  # Parameters not stored in status
            results=status.get("step_results", {}),
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at"),
            created_by=status.get("metadata", {}).get("created_by_username", "system")
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error canceling workflow execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")