import asyncio
import json
import logging
import uuid
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...core.database.models import ProcessInstance as DBProcessInstance
from ...core.database.models import WorkflowTemplate as DBWorkflowTemplate
from ...core.database.session import get_db_session

logger = logging.getLogger(__name__)

# --- Process State Management --- #
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
    type: str
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    retry_config: Optional[Dict[str, Any]] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowTemplate:
    id: str
    name: str
    description: Optional[str] = None
    version: str
    steps: List[ProcessStep]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessInstance:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str
    template_name: str
    batch_id: Optional[str] = None
    state: ProcessState = ProcessState.PENDING
    current_step_id: Optional[str] = None
    steps: List[ProcessStep] = field(default_factory=list)
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
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
        self.templates: Dict[str, WorkflowTemplate] = {}
        self._shutdown_event = asyncio.Event()
        logger.info("WorkflowManager initialized.")
    
    async def load_templates(self) -> None:
        """Load workflow templates from the database"""
        logger.info("Loading workflow templates from database")
        async with get_db_session() as session:
            query = select(DBWorkflowTemplate)
            result = await session.execute(query)
            templates = result.scalars().all()
            
            for db_template in templates:
                steps = []
                for step_data in db_template.steps:
                    steps.append(ProcessStep(**step_data))
                    
                template = WorkflowTemplate(
                    id=db_template.id,
                    name=db_template.name,
                    description=db_template.description,
                    version=db_template.version,
                    steps=steps,
                    metadata=db_template.metadata if hasattr(db_template, "metadata") else {}
                )
                self.templates[template.id] = template
                
        logger.info(f"Loaded {len(self.templates)} workflow templates")
    
    async def create_process_instance(self, template_id: str, batch_id: Optional[str] = None, 
                                     metadata: Optional[Dict[str, Any]] = None) -> ProcessInstance:
        """Create a new process instance from a workflow template"""
        logger.info(f"Creating new process instance for template {template_id}")
        
        # Load template if not already loaded
        if template_id not in self.templates:
            async with get_db_session() as session:
                db_template = await session.get(DBWorkflowTemplate, template_id)
                if not db_template:
                    raise ValueError(f"Template with ID {template_id} not found")
                
                steps = []
                for step_data in db_template.steps:
                    steps.append(ProcessStep(**step_data))
                    
                template = WorkflowTemplate(
                    id=db_template.id,
                    name=db_template.name,
                    description=db_template.description,
                    version=db_template.version,
                    steps=steps,
                    metadata=db_template.metadata if hasattr(db_template, "metadata") else {}
                )
                self.templates[template.id] = template
        
        template = self.templates[template_id]
        
        # Create process instance
        instance = ProcessInstance(
            template_id=template_id,
            template_name=template.name,
            batch_id=batch_id,
            steps=template.steps,
            metadata=metadata or {}
        )
        
        # Save to database
        async with get_db_session() as session:
            db_instance = DBProcessInstance(
                id=instance.id,
                template_id=template.id,
                batch_id=batch_id,
                state=ProcessState.PENDING.name,
                metadata=instance.metadata
            )
            session.add(db_instance)
            await session.commit()
        
        # Add to active processes
        self.active_processes[instance.id] = instance
        
        logger.info(f"Created process instance {instance.id} for template {template_id}")
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
        """Identify steps that can be executed next based on dependencies"""
        if instance.state != ProcessState.RUNNING:
            return [] # No steps can be executed if not in RUNNING state
        
        executable_steps = []
        completed_step_ids = {
            step_id for step_id, result in instance.step_results.items() 
            if result.get("status") == "completed"
        }
        
        for step in instance.steps:
            # Skip steps that are already completed or have results (even if failed)
            if step.id in instance.step_results:
                continue
                
            # Check if all dependencies are completed
            if all(dep in completed_step_ids for dep in step.dependencies):
                executable_steps.append(step)
        
        return executable_steps

    async def _execute_step(self, instance: ProcessInstance, step: ProcessStep) -> None:
        instance.current_step_id = step.id
        logger.info(f"Executing step {step.id} ('{step.name}') in process {instance.id}")
        
        # Update DB with current step
        async with get_db_session() as session:
            db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, instance.id)
            if db_instance:
                db_instance.current_step_id = step.id
                await session.commit()
        
        try:
            # Step execution logic would vary based on step type
            # This is a simplified version that just mocks step execution
            if step.type == "calibration":
                await self._execute_calibration_step(instance, step)
            elif step.type == "alignment":
                await self._execute_alignment_step(instance, step)
            elif step.type == "inspection":
                await self._execute_inspection_step(instance, step)
            elif step.type == "assembly":
                await self._execute_assembly_step(instance, step)
            else:
                # Default execution for unknown types
                # In production, you'd probably want to fail these
                logger.warning(f"Unknown step type '{step.type}' for step {step.id} in process {instance.id}")
                await asyncio.sleep(1)  # Simulate some work
                instance.mark_step_complete(step.id, {"message": "Unknown step type executed with default handling"})
        
        except Exception as e:
            logger.exception(f"Error executing step {step.id} ('{step.name}') in process {instance.id}: {e}")
            instance.mark_step_failed(step.id, str(e))
            # Handle retry logic if implemented (not in this basic version)
            if step.validation_rules.get("critical", False): 
                instance.state = ProcessState.FAILED
        finally:
            if instance.current_step_id == step.id: # If this was the current step
                 instance.current_step_id = None # Clear current step after execution
    
    async def _execute_calibration_step(self, instance: ProcessInstance, step: ProcessStep) -> None:
        # Mock implementation - would connect to actual calibration hardware in production
        logger.info(f"Executing calibration step {step.id} in process {instance.id}")
        await asyncio.sleep(1)  # Simulate calibration work
        instance.mark_step_complete(step.id, {"calibrated": True, "accuracy": 0.99})

    async def _execute_alignment_step(self, instance: ProcessInstance, step: ProcessStep) -> None:
        # Mock implementation - would connect to actual alignment hardware in production
        logger.info(f"Executing alignment step {step.id} in process {instance.id}")
        await asyncio.sleep(1.5)  # Simulate alignment work
        instance.mark_step_complete(step.id, {"aligned": True, "position": [0.001, 0.002, 0.003]})

    async def _execute_inspection_step(self, instance: ProcessInstance, step: ProcessStep) -> None:
        # Mock implementation - would connect to actual inspection hardware in production
        logger.info(f"Executing inspection step {step.id} in process {instance.id}")
        await asyncio.sleep(0.8)  # Simulate inspection work
        instance.mark_step_complete(step.id, {"passed": True, "measurements": {"value1": 0.5, "value2": 0.7}})

    async def _execute_assembly_step(self, instance: ProcessInstance, step: ProcessStep) -> None:
        # Mock implementation - would connect to actual assembly hardware in production
        logger.info(f"Executing assembly step {step.id} in process {instance.id}")
        await asyncio.sleep(2)  # Simulate assembly work
        instance.mark_step_complete(step.id, {"assembled": True, "position_error": 0.01})

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
            # Try to load from DB for non-active but historical processes
            async with get_db_session() as session:
                db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, process_id)
                if not db_instance:
                    raise ValueError(f"Process {process_id} not found.")
                # Reconstruct a simplified status from DB record
                return {
                    "id": db_instance.id,
                    "template_id": db_instance.template_id,
                    "template_name": "",  # Would need to load from template
                    "batch_id": db_instance.batch_id,
                    "state": db_instance.state,
                    "current_step_id": db_instance.current_step_id,
                    "started_at": db_instance.started_at.isoformat() if db_instance.started_at else None,
                    "completed_at": db_instance.completed_at.isoformat() if db_instance.completed_at else None,
                    "metadata": db_instance.metadata,
                    "progress_percentage": 0.0,  # Cannot calculate without step data
                    "step_results": {}  # Would need to load step results
                }

    async def pause_process(self, process_id: str) -> None:
        """Pause a running process"""
        if process_id not in self.active_processes:
            raise ValueError(f"Process {process_id} not found.")
            
        instance = self.active_processes[process_id]
        if instance.state != ProcessState.RUNNING:
            raise ValueError(f"Process {process_id} is not in RUNNING state (current: {instance.state.name}).")
            
        instance.state = ProcessState.PAUSED
        
        # Update DB
        async with get_db_session() as session:
            db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, process_id)
            if db_instance:
                db_instance.state = ProcessState.PAUSED.name
                await session.commit()
                
        logger.info(f"Process {process_id} paused.")

    async def resume_process(self, process_id: str) -> None:
        """Resume a paused process"""
        if process_id not in self.active_processes:
            raise ValueError(f"Process {process_id} not found.")
            
        instance = self.active_processes[process_id]
        if instance.state != ProcessState.PAUSED:
            raise ValueError(f"Process {process_id} is not in PAUSED state (current: {instance.state.name}).")
            
        instance.state = ProcessState.RUNNING
        
        # Update DB
        async with get_db_session() as session:
            db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, process_id)
            if db_instance:
                db_instance.state = ProcessState.RUNNING.name
                await session.commit()
                
        logger.info(f"Process {process_id} resumed.")
        asyncio.create_task(self._execute_process(instance))

    async def abort_process(self, process_id: str) -> None:
        """Abort a process (can be in any state)"""
        if process_id not in self.active_processes:
            raise ValueError(f"Process {process_id} not found.")
            
        instance = self.active_processes[process_id]
        prev_state = instance.state
        instance.state = ProcessState.ABORTED
        instance.completed_at = datetime.utcnow()
        
        # Update DB
        async with get_db_session() as session:
            db_instance: Optional[DBProcessInstance] = await session.get(DBProcessInstance, process_id)
            if db_instance:
                db_instance.state = ProcessState.ABORTED.name
                db_instance.completed_at = instance.completed_at
                await session.commit()
                
        logger.info(f"Process {process_id} aborted (previous state: {prev_state.name}).")

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