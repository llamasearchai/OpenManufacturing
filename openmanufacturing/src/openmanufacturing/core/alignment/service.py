import asyncio
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from pydantic import BaseModel # Moved import to top

from .alignment_engine import AlignmentEngine, AlignmentParameters, MockMotionController, CalibrationProfile # Mock dependencies for now
# from ..vision.image_processing import ImageProcessor # Actual ImageProcessor
# from ..hardware.motion_controller import MotionController # Actual MotionController

logger = logging.getLogger(__name__)

class AlignmentTaskStatus(BaseModel):
    request_id: str
    device_id: str
    status: str # e.g., "pending", "in_progress", "completed", "failed", "cancelled"
    result: Optional[Dict[str, Any]] = None # Full result from AlignmentEngine
    error_message: Optional[str] = None
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class AlignmentService:
    def __init__(
        self,
        motion_controller: Any, # Should be a proper MotionController instance
        image_processor: Any,   # Should be a proper ImageProcessor instance
        calibration_profile: Any # Should be a proper CalibrationProfile instance
    ):
        # In a real app, these would be actual hardware/software components
        # For this example, we might pass mocks or simplified versions
        self.motion_controller = motion_controller if motion_controller else MockMotionController()
        # self.image_processor = image_processor
        self.calibration_profile = calibration_profile if calibration_profile else CalibrationProfile()
        
        # Store for ongoing and completed alignment tasks
        self.alignment_tasks: Dict[str, AlignmentTaskStatus] = {}
        self._active_engines: Dict[str, AlignmentEngine] = {}
        logger.info("AlignmentService initialized.")

    async def _run_alignment_task(self, engine: AlignmentEngine, task_status: AlignmentTaskStatus):
        logger.info(f"Starting alignment task {task_status.request_id} for device {task_status.device_id}")
        task_status.status = "in_progress"
        task_status.started_at = datetime.utcnow()
        try:
            # Parameters for the align method could come from the initial request or be defaults
            # Here, using the engine's default parameters or those set during its init.
            result = await engine.align()
            task_status.result = result
            if result.get("success"):
                task_status.status = "completed"
            elif result.get("cancelled"):
                task_status.status = "cancelled"
                task_status.error_message = result.get("final_status_message", "Alignment cancelled")
            else:
                task_status.status = "failed"
                task_status.error_message = result.get("final_status_message", "Alignment failed")
            logger.info(f"Alignment task {task_status.request_id} finished with status: {task_status.status}")
        except Exception as e:
            logger.error(f"Exception in alignment task {task_status.request_id}: {e}", exc_info=True)
            task_status.status = "failed"
            task_status.error_message = str(e)
            if task_status.result is None: # Ensure result is not None if an exception occurred before result was set
                task_status.result = {"success": False, "error": str(e)}
        finally:
            task_status.completed_at = datetime.utcnow()
            if task_status.request_id in self._active_engines:
                del self._active_engines[task_status.request_id]

    async def align_device(
        self, 
        request_id: str,
        device_id: str, 
        parameters: AlignmentParameters, 
        process_id: Optional[str] = None, 
        batch_id: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        logger.info(f"Received alignment request {request_id} for device {device_id}.")
        
        # Create and initialize a new AlignmentEngine for this task
        # In a real system, motion_controller might be specific to device_id
        # Or a shared motion_controller that can handle multiple devices/axes is used.
        # For simplicity, assuming one shared motion_controller for now.
        engine = AlignmentEngine(
            motion_controller=self.motion_controller, # This needs to be a valid controller
            calibration_profile=self.calibration_profile, # This needs to be valid
            parameters=parameters
        )
        self._active_engines[request_id] = engine
        
        task_status = AlignmentTaskStatus(
            request_id=request_id,
            device_id=device_id,
            status="pending",
            submitted_at=datetime.utcnow()
        )
        self.alignment_tasks[request_id] = task_status
        
        # Run the alignment in the background without awaiting it here
        asyncio.create_task(self._run_alignment_task(engine, task_status))
        
        return request_id

    async def get_alignment_result(self, request_id: str) -> Optional[AlignmentTaskStatus]:
        task = self.alignment_tasks.get(request_id)
        if task:
            # Potentially map to the API response model (AlignmentResultData) here or in the route
            return task 
        return None

    async def get_alignment_history(self, device_id: str, limit: int = 10) -> List[AlignmentTaskStatus]:
        # This is a simplified history; a real one might query a database
        device_history = []
        # Iterate in reverse chronological order of submission
        for task_status in sorted(self.alignment_tasks.values(), key=lambda t: t.submitted_at, reverse=True):
            if task_status.device_id == device_id:
                device_history.append(task_status)
            if len(device_history) >= limit:
                break
        return device_history

    async def cancel_alignment(self, request_id: str) -> bool:
        logger.info(f"Attempting to cancel alignment task {request_id}")
        task_status = self.alignment_tasks.get(request_id)
        engine_to_stop = self._active_engines.get(request_id)

        if task_status and task_status.status in ["pending", "in_progress"]:
            if engine_to_stop:
                engine_to_stop.request_stop_alignment()
                # Status will be updated to "cancelled" by the _run_alignment_task itself when it finishes
                logger.info(f"Stop requested for active alignment engine {request_id}")
                return True
            else:
                # If pending and no engine yet, can mark as cancelled directly
                if task_status.status == "pending":
                    task_status.status = "cancelled"
                    task_status.error_message = "Cancelled before starting"
                    task_status.completed_at = datetime.utcnow()
                    logger.info(f"Task {request_id} was pending and is now cancelled.")
                    return True
        logger.warning(f"Could not cancel task {request_id}. Status: {task_status.status if task_status else 'Not Found'}")
        return False 