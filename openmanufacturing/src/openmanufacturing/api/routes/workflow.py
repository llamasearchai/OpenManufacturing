from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

# Assuming a WorkflowService and Workflow models exist in core
# from ...core.process.service import WorkflowTemplateService # Example path for template service
# from ...core.process.models import WorkflowTemplate, WorkflowTemplateCreate, WorkflowTemplateUpdate # Example models

from ..dependencies import get_current_active_user, get_process_manager # For authentication and process interaction
from ..dependencies import User as PydanticUser # Pydantic user model
from ...core.process.workflow_manager import WorkflowManager, ProcessStep as CoreProcessStep # Core models

router = APIRouter()

# --- Mock Workflow Template Data and Service (Replace with actual service and DB interaction) --- #

mock_workflow_templates_db: Dict[str, Any] = {
    "wf-template-001": {
        "id": "wf-template-001", 
        "name": "Standard Fiber Alignment", 
        "description": "A standard workflow for fiber to chip alignment.",
        "version": "1.0",
        "steps": [
            {"id": "step1", "name": "Coarse Align", "component": "alignment", "parameters": {"type": "coarse"}},
            {"id": "step2", "name": "Fine Align", "component": "alignment", "parameters": {"type": "fine"}, "dependencies": ["step1"]}
        ]
    }
}

class MockWorkflowTemplateService:
    async def get_templates(self, skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        return list(mock_workflow_templates_db.values())[skip : skip + limit]

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        return mock_workflow_templates_db.get(template_id)

    async def create_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        template_id = template_data.get("id", f"wf-template-{len(mock_workflow_templates_db) + 1:03d}")
        if template_id in mock_workflow_templates_db:
            raise ValueError("Workflow Template ID already exists")
        new_template = template_data.copy()
        new_template["id"] = template_id
        mock_workflow_templates_db[template_id] = new_template
        return new_template
    # Add update and delete methods as needed

async def get_workflow_template_service(): # In a real app, this would come from DI
    return MockWorkflowTemplateService()

# --- Pydantic Models for Workflow Template API --- #

class ProcessStep(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    component: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    dependencies: List[str] = Field(default_factory=list)
    validation_rules: Dict[str, Any] = Field(default_factory=dict)

class WorkflowTemplateBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    version: str = Field("1.0.0", description="Semantic version of the workflow template")
    steps: List[ProcessStep]

class WorkflowTemplateCreate(WorkflowTemplateBase):
    id: Optional[str] = Field(None, description="Optional template ID, can be auto-generated or user-defined based on system")

class WorkflowTemplateResponse(WorkflowTemplateBase):
    id: str
    # Add other fields like created_at, updated_at if available from service

# --- API Endpoints for Workflow Templates --- #

@router.post("/templates", response_model=WorkflowTemplateResponse, status_code=201, summary="Create a new workflow template")
async def create_workflow_template(
    template_in: WorkflowTemplateCreate,
    current_user: PydanticUser = Depends(get_current_active_user),
    template_service: MockWorkflowTemplateService = Depends(get_workflow_template_service)
):
    try:
        # Convert Pydantic ProcessStep models to dicts if core service expects that
        # For this mock, assuming model_dump() is sufficient
        created_template = await template_service.create_template(template_in.model_dump())
        return WorkflowTemplateResponse(**created_template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating workflow template: {str(e)}")

@router.get("/templates", response_model=List[WorkflowTemplateResponse], summary="List all workflow templates")
async def list_workflow_templates(
    skip: int = 0,
    limit: int = 10,
    current_user: PydanticUser = Depends(get_current_active_user),
    template_service: MockWorkflowTemplateService = Depends(get_workflow_template_service)
):
    templates = await template_service.get_templates(skip=skip, limit=limit)
    return [WorkflowTemplateResponse(**t) for t in templates]

@router.get("/templates/{template_id}", response_model=WorkflowTemplateResponse, summary="Get a specific workflow template")
async def get_workflow_template(
    template_id: str,
    current_user: PydanticUser = Depends(get_current_active_user),
    template_service: MockWorkflowTemplateService = Depends(get_workflow_template_service)
):
    template = await template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return WorkflowTemplateResponse(**template)

# Note: Endpoints for Process Instances (running workflows) are typically in a separate `process.py` router.
# This `workflow.py` router focuses on templates. 