import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

# Assuming these are placeholder paths and will be correctly structured
# from ..database.models import WorkflowTemplate as DBWorkflowTemplate, ProcessInstance as DBProcessInstance # SQLAlchemy models
# from ..database.db import get_db_session
# from ..alignment.alignment_engine import AlignmentEngine # Actual engine

logger = logging.getLogger(__name__)

# --- Placeholder/Mock DB Models and Session (to be replaced with actual DB integration) --- #
class MockBaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class DBWorkflowTemplate(MockBaseModel): # Mock SQLAlchemy model
    id: str
    name: str
    description: Optional[str]
    steps_json: str # Store steps as JSON string in mock
    # Add other fields like version, created_at, etc.

class DBProcessInstance(MockBaseModel): # Mock SQLAlchemy model
    id: str
    template_id: str
    batch_id: Optional[str]
    state: str
    current_step_id: Optional[str]
    # step_results_json: str # In a real DB, results might be in a separate table or JSONB
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    metadata_json: Optional[str] # Store metadata as JSON

mock_db_templates: Dict[str, DBWorkflowTemplate] = {}
mock_db_instances: Dict[str, DBProcessInstance] = {}

class MockAsyncSession:
    async def get(self, model_cls: Type[MockBaseModel], instance_id: str) -> Optional[MockBaseModel]:
        if model_cls == DBWorkflowTemplate:
            return mock_db_templates.get(instance_id)
        elif model_cls == DBProcessInstance:
            return mock_db_instances.get(instance_id)
        return None

    def add(self, instance: MockBaseModel):
        if isinstance(instance, DBWorkflowTemplate):
            mock_db_templates[instance.id] = instance
        elif isinstance(instance, DBProcessInstance):
            mock_db_instances[instance.id] = instance
        logger.debug(f"Mock DB: Added instance {instance.id} of type {type(instance).__name__}")

    async def commit(self):
        logger.debug("Mock DB: Commit called.")
        await asyncio.sleep(0.01) # Simulate commit delay

    async def refresh(self, instance: MockBaseModel):
        logger.debug(f"Mock DB: Refresh called for {instance.id}.")
        await asyncio.sleep(0.01)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

async def get_db_session() -> MockAsyncSession: # This function would provide the actual SQLAlchemy session
    return MockAsyncSession()

import json # For serializing/deserializing steps/metadata for mock DB
# --- End of Placeholder/Mock DB --- # 

class ProcessState(Enum):
    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    ABORTED = auto()

@dataclass
class ProcessStep:
    id: str
    name: str
    description: str
    component: str  # Reference to component (e.g., "alignment_service", "custom_script_runner")
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowTemplate: # This is the in-memory representation of a template
    id: str
    name: str
    description: Optional[str] = None
    steps: List[ProcessStep] = field(default_factory=list)
    # Add version, etc. if needed

@dataclass
class ProcessInstance: # This is the in-memory representation of a running/completed process
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str
    template_name: str # Added for easier reference
    batch_id: Optional[str] = None
    state: ProcessState = ProcessState.PENDING
    current_step_id: Optional[str] = None
    steps: List[ProcessStep] = field(default_factory=list) # Copied from template at instantiation
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict) # Stores status, timestamp, data/error
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_step_complete(self, step_id: str, result_data: Any) -> None:
        self.step_results[step_id] = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": result_data
        }
        logger.info(f"Process {self.id}, Step {step_id}: marked complete.")
    
    def mark_step_failed(self, step_id: str, error_message: str) -> None:
        self.step_results[step_id] = {
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_message
        }
        logger.error(f"Process {self.id}, Step {step_id}: marked failed. Error: {error_message}")
    
    def get_progress_percentage(self) -> float:
        if not self.steps:
            return 0.0
        completed_step_count = sum(1 for step_id in self.step_results 
                                   if self.step_results[step_id].get("status") == "completed")
        return (completed_step_count / len(self.steps)) * 100 if self.steps else 0.0

class WorkflowManager:
    def __init__(self):
        self.active_processes: Dict[str, ProcessInstance] = {}
        self.component_registry: Dict[str, Any] = {} # Maps component name to service/object that can execute it
        self._shutdown_event = asyncio.Event()
        logger.info("WorkflowManager initialized.")
        
    def register_component(self, name: str, component_executor: Any) -> None:
        self.component_registry[name] = component_executor
        logger.info(f"Component '{name}' registered with WorkflowManager.")
    
    async def load_workflow_template(self, template_id: str) -> WorkflowTemplate:
        async with get_db_session() as session:
            db_template: Optional[DBWorkflowTemplate] = await session.get(DBWorkflowTemplate, template_id)
            if not db_template:
                raise ValueError(f"Workflow template '{template_id}' not found in mock DB.")
            
            # Deserialize steps from JSON (assuming steps_json in mock DB)
            try:
                steps_data = json.loads(db_template.steps_json) if db_template.steps_json else []
                steps = [ProcessStep(**step_data) for step_data in steps_data]
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding steps_json for template {template_id}: {e}")
                raise ValueError(f"Invalid steps format in template {template_id}.")

            return WorkflowTemplate(
                id=db_template.id,
                name=db_template.name,
                description=db_template.description,
                steps=steps
            )
    
    async def create_process_instance(self, template_id: str, batch_id: Optional[str] = None,
                                    metadata: Optional[Dict[str, Any]] = None) -> ProcessInstance:
        template = await self.load_workflow_template(template_id)
        
        instance = ProcessInstance(
            template_id=template.id,
            template_name=template.name,
            batch_id=batch_id,
            steps=template.steps, # Deep copy steps if they can be modified per instance
            metadata=metadata or {}
        )
        
        async with get_db_session() as session:
            db_instance = DBProcessInstance(
                id=instance.id,
                template_id=instance.template_id,
                batch_id=instance.batch_id,
                state=instance.state.name, # Store enum name as string
                metadata_json=json.dumps(instance.metadata) if instance.metadata else None
            )
            session.add(db_instance)
            await session.commit()
        
        self.active_processes[instance.id] = instance
        logger.info(f"Created ProcessInstance {instance.id} from Template {template_id} ('{template.name}').")
        return instance
    
    async def start_process(self, process_id: str) -> None:
        if process_id not in self.active_processes:
            # Potentially load from DB if not in active_processes (e.g., after a restart)
            raise ValueError(f"Process {process_id} not found or not active.")
        
        instance = self.active_processes[process_id]
        if instance.state != ProcessState.PENDING:
            raise ValueError(f"Process {process_id} is not in PENDING state (current: {instance.state.name}).")
            
        instance.state = ProcessState.RUNNING
        instance.started_at = datetime.utcnow()
        
        async with get_db_session() as session:
            db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, process_id)
            if db_instance:
                db_instance.state = ProcessState.RUNNING.name
                db_instance.started_at = instance.started_at
                await session.commit()
        
        logger.info(f"Starting execution of Process {process_id}.")
        asyncio.create_task(self._execute_process(instance))

    async def _execute_process(self, instance: ProcessInstance) -> None:
        logger.info(f"Executing process {instance.id} ('{instance.template_name}')")
        try:
            next_steps_to_run = self._get_executable_steps(instance)
            while next_steps_to_run and instance.state == ProcessState.RUNNING:
                await asyncio.gather(*[self._execute_step(instance, step) for step in next_steps_to_run])
                
                if instance.state != ProcessState.RUNNING: # Check if state changed (e.g., failed, paused)
                    break
                
                next_steps_to_run = self._get_executable_steps(instance)
                if not next_steps_to_run and not self._is_process_complete(instance):
                    # This could indicate a deadlock or an issue if process is not yet complete
                    all_steps_accounted_for = all(s.id in instance.step_results for s in instance.steps)
                    if not all_steps_accounted_for:
                        logger.warning(f"Process {instance.id} has no executable steps but is not complete. Possible deadlock or error.")
                        # For now, let it wait or add a timeout logic for stuck processes
                        await asyncio.sleep(1) # Avoid tight loop if stuck
                    else: # All steps have results, determine final state
                        break 
                elif not next_steps_to_run and self._is_process_complete(instance):
                    break # Process is complete

            # Final state determination
            if instance.state == ProcessState.RUNNING: # If loop exited normally while still running
                if self._is_process_complete(instance) and all(res.get("status") == "completed" for res in instance.step_results.values()):
                    instance.state = ProcessState.COMPLETED
                    logger.info(f"Process {instance.id} completed successfully.")
                else:
                    instance.state = ProcessState.FAILED # Or incomplete, if some steps failed
                    logger.error(f"Process {instance.id} finished in RUNNING state but not all steps succeeded or completed.")
            
        except Exception as e:
            logger.exception(f"Critical error during execution of process {instance.id}: {e}")
            instance.state = ProcessState.FAILED
            # Mark all ongoing or pending steps as failed/aborted if applicable
        finally:
            instance.completed_at = datetime.utcnow()
            async with get_db_session() as session:
                db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, instance.id)
                if db_instance:
                    db_instance.state = instance.state.name
                    db_instance.completed_at = instance.completed_at
                    # db_instance.step_results_json = json.dumps(instance.step_results) # Persist results
                    await session.commit()
            logger.info(f"Process {instance.id} execution finished with state: {instance.state.name}")

    def _is_process_complete(self, instance: ProcessInstance) -> bool:
        return len(instance.step_results) == len(instance.steps)

    def _get_executable_steps(self, instance: ProcessInstance) -> List[ProcessStep]:
        executable = []
        for step in instance.steps:
            if step.id in instance.step_results: # Already has a result (completed, failed, retrying)
                if instance.step_results[step.id].get("status") == "retrying": # Logic for retrying can be added here
                    pass # Potentially re-add if retry logic permits
                continue

            # Check dependencies
            dependencies_met = True
            for dep_id in step.dependencies:
                if dep_id not in instance.step_results or instance.step_results[dep_id].get("status") != "completed":
                    dependencies_met = False
                    break
            if dependencies_met:
                executable.append(step)
        return executable

    async def _execute_step(self, instance: ProcessInstance, step: ProcessStep) -> None:
        instance.current_step_id = step.id
        logger.info(f"Process {instance.id}: Executing Step '{step.name}' (ID: {step.id}) with component '{step.component}'.")
        
        executor = self.component_registry.get(step.component)
        if not executor:
            logger.error(f"Component executor '{step.component}' not found for step {step.id} in process {instance.id}.")
            instance.mark_step_failed(step.id, f"Component executor '{step.component}' not registered.")
            # If this step is critical, fail the whole process
            if step.validation_rules.get("critical", False):
                 instance.state = ProcessState.FAILED
            return

        try:
            # Assume executor has an async `execute` method matching (params: Dict) -> Any
            # The `execute` method itself should handle its own logic, including interaction with hardware/services
            step_execution_task = executor.execute(**step.parameters) # Unpack parameters for the component method
            
            if step.timeout_seconds:
                result_data = await asyncio.wait_for(step_execution_task, timeout=step.timeout_seconds)
            else:
                result_data = await step_execution_task
            
            # TODO: Add validation of result_data against step.validation_rules
            # self._validate_step_result(result_data, step.validation_rules)
            
            instance.mark_step_complete(step.id, result_data)
            
        except asyncio.TimeoutError:
            logger.error(f"Step {step.id} ('{step.name}') in process {instance.id} timed out after {step.timeout_seconds}s.")
            instance.mark_step_failed(step.id, "Execution timed out.")
            if step.validation_rules.get("critical", False): instance.state = ProcessState.FAILED
        except Exception as e:
            logger.exception(f"Error executing step {step.id} ('{step.name}') in process {instance.id}: {e}")
            instance.mark_step_failed(step.id, str(e))
            # Handle retry logic if implemented (not in this basic version)
            if step.validation_rules.get("critical", False): instance.state = ProcessState.FAILED
        finally:
            if instance.current_step_id == step.id: # If this was the current step
                 instance.current_step_id = None # Clear current step after execution

    # ... (pause_process, resume_process, abort_process from main.txt to be added) ...
    async def get_process_status(self, process_id: str) -> Dict[str, Any]:
        if process_id in self.active_processes:
            instance = self.active_processes[process_id]
            return {
                "id": instance.id,
                "template_id": instance.template_id,
                "template_name": instance.template_name,
                "batch_id": instance.batch_id,
                "state": instance.state.name,
                "current_step_id": instance.current_step_id,
                "started_at": instance.started_at.isoformat() if instance.started_at else None,
                "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
                "metadata": instance.metadata,
                "progress_percentage": instance.get_progress_percentage(),
                "step_results": instance.step_results
            }
        else:
            # Optionally, try to load from DB for non-active but historical processes
            async with get_db_session() as session:
                db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, process_id)
                if not db_instance:
                    raise ValueError(f"Process {process_id} not found.")
                # Reconstruct a simplified status from DB record
                return {
                    "id": db_instance.id,
                    "template_id": db_instance.template_id,
                    "state": db_instance.state,
                    "started_at": db_instance.started_at.isoformat() if db_instance.started_at else None,
                    "completed_at": db_instance.completed_at.isoformat() if db_instance.completed_at else None,
                     # Cannot easily get progress or full step results without more DB structure
                }

    async def shutdown(self):
        logger.info("WorkflowManager shutting down. Aborting active processes...")
        self._shutdown_event.set()
        active_tasks = []
        for pid, instance in self.active_processes.items():
            if instance.state == ProcessState.RUNNING or instance.state == ProcessState.PAUSED:
                logger.info(f"Requesting abort for active process {pid} due to shutdown.")
                # This abort should ideally be an async operation if it involves external communication
                instance.state = ProcessState.ABORTED # Mark as aborted
                # Persist this state change to DB
                async with get_db_session() as session:
                    db_inst: Optional[DBProcessInstance] = await session.get(DBProcessInstance, pid)
                    if db_inst:
                        db_inst.state = ProcessState.ABORTED.name
                        db_inst.completed_at = datetime.utcnow()
                        await session.commit()
        # Wait for any background tasks related to process execution to complete if possible
        # This is simplified; real graceful shutdown is more complex.
        logger.info("WorkflowManager shutdown complete.")

# Mock component for testing WorkflowManager
class MockAlignmentComponent:
    async def execute(self, type: str):
        logger.info(f"MockAlignmentComponent executing with type: {type}")
        await asyncio.sleep(np.random.uniform(0.1, 0.5)) # Simulate work
        if type == "error_step":
            raise RuntimeError("Simulated error in alignment step")
        return {"alignment_type": type, "status": "mock success", "power": -np.random.uniform(1,5)}

import numpy as np # For mock component random delays

async def main_workflow_test():
    logging.basicConfig(level=logging.DEBUG)
    
    # Setup Mock DB with a template
    steps_list = [
        {"id": "s1", "name": "Coarse Align", "description": "Coarse alignment phase", "component": "aligner", "parameters": {"type": "coarse"}},
        {"id": "s2", "name": "Fine Align", "description": "Fine alignment phase", "component": "aligner", "parameters": {"type": "fine"}, "dependencies": ["s1"]},
        {"id": "s3", "name": "Error Step (for testing)", "description": "A step designed to fail", "component": "aligner", "parameters": {"type": "error_step"}, "dependencies": ["s1"]}
    ]
    template1_id = "test-template-1"
    mock_db_templates[template1_id] = DBWorkflowTemplate(
        id=template1_id, 
        name="Test Alignment Workflow", 
        steps_json=json.dumps(steps_list)
    )

    wm = WorkflowManager()
    aligner_component = MockAlignmentComponent()
    wm.register_component("aligner", aligner_component)

    try:
        instance = await wm.create_process_instance(template_id=template1_id, batch_id="batch-007")
        print(f"Created instance: {instance.id} for template '{instance.template_name}'")

        await wm.start_process(instance.id)
        
        # Wait for it to complete or fail (in a real app, this would be non-blocking)
        while instance.state in [ProcessState.PENDING, ProcessState.RUNNING]:
            status = await wm.get_process_status(instance.id)
            print(f"Instance {instance.id} Status: {status.get('state')}, Progress: {status.get('progress_percentage'):.2f}%, Current Step: {status.get('current_step_id')}")
            await asyncio.sleep(0.2)
        
        final_status = await wm.get_process_status(instance.id)
        print(f"Final Instance {instance.id} Status: {final_status.get('state')}")
        print("Step Results:")
        for step_id, res_info in final_status.get("step_results", {}).items():
            print(f"  Step {step_id}: {res_info.get('status')}, Data/Error: {res_info.get('data') or res_info.get('error')}")

    except ValueError as ve:
        print(f"Error: {ve}")
    finally:
        await wm.shutdown()

if __name__ == "__main__":
    asyncio.run(main_workflow_test()) 