import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


from ..database.db import get_db_session # Changed back from get_session
from ..database.models import ( # Added for F821
    AlignmentResult,
    Device,
    ProcessInstance,
)
from ..hardware.motion_controller import MotionController
from ..process.calibration import CalibrationProfile
from ..vision.image_processing import ImageProcessor
from .alignment_engine import AlignmentEngine, AlignmentParameters

logger = logging.getLogger(__name__)


class AlignmentService:
    """Service for performing optical alignments"""

    def __init__(
        self,
        motion_controller: MotionController,
        image_processor: ImageProcessor,
        calibration_profile: CalibrationProfile,
    ):
        """
        Initialize alignment service

        Args:
            motion_controller: Motion controller instance
            image_processor: Image processor instance
            calibration_profile: Calibration profile instance
        """
        self.motion_controller = motion_controller
        self.image_processor = image_processor
        self.calibration_profile = calibration_profile

        # Create alignment engine
        self.engine = AlignmentEngine(
            motion_controller=motion_controller, calibration_profile=calibration_profile
        )

        # Track active and completed alignments
        self.active_alignments: Dict[str, Dict[str, Any]] = {}
        self.completed_alignments: Dict[str, Dict[str, Any]] = {}
        self.alignment_history: Dict[str, List[Dict[str, Any]]] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info("Alignment service initialized")

    async def align_device(
        self,
        request_id: str,
        device_id: str,
        parameters: Optional[AlignmentParameters] = None,
        process_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start alignment process for a device

        Args:
            request_id: Unique ID for this alignment request
            device_id: Device ID to align
            parameters: Optional alignment parameters
            process_id: Optional process ID this alignment is part of
            metadata: Optional metadata

        Returns:
            Request ID for tracking this alignment
        """
        # Create result structure
        current_time = datetime.now()
        result_payload = {
            "request_id": request_id,
            "device_id": device_id,
            "process_id": process_id,
            "parameters": (
                parameters.model_dump() if parameters else AlignmentParameters().model_dump()
            ),
            "metadata": metadata or {},
            "status": "scheduled",  # Changed from "started" to "scheduled"
            "timestamp": current_time.isoformat(),
            "success": False,
            "optical_power_dbm": None,  # Initialize to None
            "position": None,  # Initialize to None
            "duration_ms": 0,
            "iterations": 0,
            "error": None,
            "trajectory": [],  # Initialize trajectory
        }

        # Store in active alignments
        async with self._lock:
            self.active_alignments[request_id] = result_payload

        # Start alignment in background
        asyncio.create_task(
            self._perform_alignment(request_id, device_id, parameters, process_id, metadata)
        )  # Pass all necessary info

        logger.info(f"Scheduled alignment for device {device_id}, request ID: {request_id}")
        return request_id

    async def _perform_alignment(
        self,
        request_id: str,
        device_id: str,
        parameters: Optional[AlignmentParameters],
        process_id: Optional[str],  # Added
        metadata: Optional[Dict[str, Any]],
    ) -> None:  # Added
        """
        Perform alignment process

        Args:
            request_id: Request ID for this alignment
            device_id: Device ID to align
            parameters: Optional alignment parameters
            process_id: Optional process ID this alignment is part of
            metadata: Optional metadata
        """
        start_time = time.time()

        try:
            # Get alignment data
            async with self._lock:
                if request_id not in self.active_alignments:
                    logger.error(f"Alignment request {request_id} not found")
                    return

                alignment_data = self.active_alignments[request_id]

            # Update status
            alignment_data["status"] = "running"
            alignment_data["timestamp"] = datetime.now().isoformat()
            # No need for _update_alignment_status call if modifying directly under lock earlier

            # Check if controller is initialized
            if not self.motion_controller._is_initialized:
                await self.motion_controller.initialize()

            # Use provided parameters or defaults
            if parameters:
                self.engine.parameters = parameters

            # Perform alignment
            result = await self.engine.align()

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Prepare data for storage and response
            final_result_data = {
                "request_id": request_id,
                "device_id": device_id,  # ensure device_id is available
                "process_id": process_id,  # ensure process_id is available
                "parameters": self.engine.parameters.model_dump(),
                "metadata": metadata or {},
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "success": result["success"],
                "optical_power_dbm": result.get("fine_alignment", {}).get("final_power_dbm"),
                "position": result.get("fine_alignment", {}).get("final_position"),
                "duration_ms": duration_ms,
                "iterations": len(result.get("history", [])),
                "error": result.get("error"),
                "trajectory": result.get("history", []),
            }

            if not result["success"] and not result.get("error"):
                final_result_data["error"] = result.get("fine_alignment", {}).get(
                    "error", "Alignment did not reach target power or failed."
                )

            # Update result in active_alignments (will be moved to completed_alignments later)
            async with self._lock:
                if request_id in self.active_alignments:
                    self.active_alignments[request_id].update(final_result_data)

            # Log success or failure
            if result["success"]:
                logger.info(
                    f"Alignment successful for request {request_id}. Power: {final_result_data['optical_power_dbm']:.2f} dBm, Position: {final_result_data['position']}"
                )
            else:
                logger.warning(
                    f"Alignment failed or did not reach target power for request {request_id}. Error: {final_result_data['error']}"
                )

        except Exception as e:
            # Handle any exceptions
            logger.exception(f"Critical error during alignment for request {request_id}: {str(e)}")

            # Update result with error
            duration_ms = int((time.time() - start_time) * 1000)
            error_result_data = {
                "request_id": request_id,
                "device_id": device_id,
                "process_id": process_id,
                "parameters": (
                    parameters.model_dump() if parameters else AlignmentParameters().model_dump()
                ),
                "metadata": metadata or {},
                "status": "failed",
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "duration_ms": duration_ms,
                "error": str(e),
                "trajectory": self.active_alignments.get(request_id, {}).get(
                    "trajectory", []
                ),  # Keep previous trajectory if any
            }
            async with self._lock:
                if request_id in self.active_alignments:
                    self.active_alignments[request_id].update(error_result_data)

        finally:
            # Move active alignment to completed and save to DB
            final_data_to_save = None
            async with self._lock:
                if request_id in self.active_alignments:
                    result_to_move = self.active_alignments.pop(request_id)
                    self.completed_alignments[request_id] = result_to_move
                    final_data_to_save = result_to_move  # Use the most up-to-date data

                    # Add to device history
                    device_id_for_history = result_to_move["device_id"]
                    if device_id_for_history:  # Ensure device_id exists
                        if device_id_for_history not in self.alignment_history:
                            self.alignment_history[device_id_for_history] = []

                        # Keep only recent history (up to 100 entries)
                        self.alignment_history[device_id_for_history].append(result_to_move)
                        if len(self.alignment_history[device_id_for_history]) > 100:
                            self.alignment_history[device_id_for_history].pop(0)

            if final_data_to_save:
                await self._save_alignment_result(final_data_to_save)

    async def _update_alignment_status(self, request_id: str, status: str) -> None:
        """
        Update alignment status

        Args:
            request_id: Request ID
            status: New status
        """
        async with self._lock:
            if request_id in self.active_alignments:
                self.active_alignments[request_id]["status"] = status
                self.active_alignments[request_id]["timestamp"] = datetime.now().isoformat()

    async def _update_alignment_result(
        self,
        request_id: str,
        status: str,
        success: bool,
        position: Optional[Dict[str, float]] = None,
        optical_power_dbm: Optional[float] = None,  # Made Optional
        duration_ms: int = 0,
        iterations: int = 0,
        error: Optional[str] = None,
        trajectory: Optional[List[Dict[str, Any]]] = None,
    ) -> None:  # Added Trajectory
        """
        Update alignment result

        Args:
            request_id: Request ID
            status: New status
            success: Whether alignment was successful
            position: Position data (x, y, z)
            optical_power_dbm: Measured optical power
            duration_ms: Duration in milliseconds
            iterations: Number of iterations performed
            error: Error message if failed
            trajectory: Movement history
        """
        async with self._lock:
            if request_id in self.active_alignments:
                result = self.active_alignments[request_id]
                result["status"] = status
                result["success"] = success

                if position:
                    result["position"] = position
                if optical_power_dbm is not None:
                    result["optical_power_dbm"] = optical_power_dbm
                if trajectory is not None:
                    result["trajectory"] = trajectory

                result["duration_ms"] = duration_ms
                result["iterations"] = iterations
                result["error"] = error
                result["timestamp"] = datetime.now().isoformat()

    async def get_alignment_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of an alignment request

        Args:
            request_id: Request ID

        Returns:
            Status data or None if not found
        """
        async with self._lock:
            # Check active alignments
            if request_id in self.active_alignments:
                return self.active_alignments[request_id].copy()

            # Check completed alignments
            if request_id in self.completed_alignments:
                return self.completed_alignments[request_id].copy()

            return None

    def get_alignment_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get result of completed alignment

        Args:
            request_id: ID of alignment request

        Returns:
            Alignment result or None if not found
        """
        # This method might be called with an async lock if it were async,
        # but for synchronous access, ensure data copying if mutable.
        # Accessing completed_alignments directly should be fine as it's updated under lock.
        return self.completed_alignments.get(request_id)

    def get_alignment_history(self, device_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get alignment history for a device

        Args:
            device_id: Device ID
            limit: Maximum number of results to return

        Returns:
            List of alignment results
        """
        if device_id not in self.alignment_history:
            return []

        # Return most recent alignments first
        return list(reversed(self.alignment_history[device_id][-limit:]))

    def cancel_alignment(self, request_id: str) -> bool:
        """
        Cancel an ongoing alignment

        Args:
            request_id: Request ID

        Returns:
            Success status
        """
        # Check if alignment is active
        active_alignment_data = None
        # Synchronous peek, actual cancellation logic is async
        if request_id in self.active_alignments:
            active_alignment_data = self.active_alignments[request_id]

        if not active_alignment_data:
            logger.warning(
                f"Alignment request {request_id} not found or not active for cancellation."
            )
            return False

        # Schedule the cancellation task
        asyncio.create_task(self._process_cancellation(request_id, active_alignment_data))

        logger.info(f"Cancellation initiated for alignment request {request_id}")
        return True

    async def _process_cancellation(self, request_id: str, alignment_data: Dict[str, Any]):
        """Helper to process cancellation asynchronously."""
        await self.motion_controller.stop()  # Stop motion

        # Update status to "cancelling" then "cancelled"
        # This uses the more robust _update_alignment_result method

        cancellation_error_message = "Alignment cancelled by user"
        current_time = datetime.now()
        duration_ms = 0
        if alignment_data.get("timestamp"):
            try:
                start_time_iso = alignment_data["timestamp"]
                # Ensure timestamp is offset-aware before subtraction if needed, or handle naive datetimes
                start_dt = datetime.fromisoformat(start_time_iso)
                # Assuming both are naive or both are offset-aware (UTC)
                duration_ms = int((current_time - start_dt).total_seconds() * 1000)
            except Exception:
                logger.warning(f"Could not calculate duration for cancelled request {request_id}")

        # Use _update_alignment_result to ensure data consistency and saving logic is triggered
        # We need to ensure that this transitions through the finally block of _perform_alignment
        # A simpler way is to set a flag that _perform_alignment checks.
        # For now, directly update and move.

        final_cancel_data = {
            "request_id": request_id,
            "device_id": alignment_data["device_id"],
            "process_id": alignment_data.get("process_id"),
            "parameters": alignment_data.get("parameters"),
            "metadata": alignment_data.get("metadata"),
            "status": "cancelled",
            "timestamp": current_time.isoformat(),
            "success": False,
            "optical_power_dbm": alignment_data.get("optical_power_dbm"),
            "position": alignment_data.get("position"),
            "duration_ms": duration_ms,
            "iterations": alignment_data.get("iterations", 0),
            "error": cancellation_error_message,
            "trajectory": alignment_data.get("trajectory", []),
        }

        async with self._lock:
            if request_id in self.active_alignments:  # Re-check if it's still active
                self.active_alignments.pop(request_id)  # Remove from active
                self.completed_alignments[request_id] = final_cancel_data  # Add to completed

                # Add to device history
                device_id = final_cancel_data["device_id"]
                if device_id:
                    if device_id not in self.alignment_history:
                        self.alignment_history[device_id] = []
                    self.alignment_history[device_id].append(final_cancel_data)
                    if len(self.alignment_history[device_id]) > 100:
                        self.alignment_history[device_id].pop(0)
            elif (
                request_id in self.completed_alignments
                and self.completed_alignments[request_id]["status"] != "cancelled"
            ):
                # If it somehow completed before cancellation took full effect, update its status
                self.completed_alignments[request_id].update(
                    {
                        "status": "cancelled",
                        "error": self.completed_alignments[request_id].get("error", "")
                        + "; "
                        + cancellation_error_message,
                        "timestamp": current_time.isoformat(),
                    }
                )
                final_cancel_data = self.completed_alignments[request_id]  # for saving
            else:  # Already cancelled or unknown
                logger.warning(
                    f"Alignment {request_id} was not active or already processed during cancellation."
                )
                return

        await self._save_alignment_result(final_cancel_data)
        logger.info(f"Alignment request {request_id} processed as cancelled.")

    async def _save_alignment_result(self, result_data: Dict[str, Any]) -> None:
        """
        Save alignment result to database

        Args:
            result_data: Alignment result dictionary
        """
        try:
            async with get_db_session() as session:
                # Check if device exists
                device_id = result_data.get("device_id")
                device = None
                if device_id:
                    device = await session.get(Device, device_id)
                    if not device:
                        logger.warning(
                            f"Device {device_id} not found in database for alignment result {result_data['request_id']}"
                        )
                else:
                    logger.warning(
                        f"Device ID missing in alignment result {result_data['request_id']}, cannot save to DB fully."
                    )
                    # Depending on requirements, might still save partial data or skip.
                    # For now, we will proceed but device_id in DB will be null if not found.

                # Check if process exists
                process_id = result_data.get("process_id")
                process = None
                if process_id:
                    process = await session.get(ProcessInstance, process_id)
                    if not process:
                        logger.warning(
                            f"Process {process_id} not found in database for alignment result {result_data['request_id']}"
                        )

                # Create alignment result
                db_result = AlignmentResult(
                    id=result_data["request_id"],
                    success=result_data["success"],
                    optical_power_dbm=result_data.get("optical_power_dbm"),
                    position_x=result_data.get("position", {}).get("x"),
                    position_y=result_data.get("position", {}).get("y"),
                    position_z=result_data.get("position", {}).get("z"),
                    duration_ms=result_data.get("duration_ms"),
                    iterations=result_data.get("iterations"),
                    alignment_method="GRADIENT_DESCENT",  # Placeholder, consider making this dynamic
                    parameters=result_data.get("parameters"),  # Save parameters used
                    trajectory=result_data.get("trajectory"),  # Save trajectory
                    error=result_data.get("error"),
                    timestamp=(
                        datetime.fromisoformat(result_data["timestamp"])
                        if isinstance(result_data["timestamp"], str)
                        else result_data["timestamp"]
                    ),
                    device_id=device.id if device else None,  # Store actual device.id
                    process_id=process.id if process else None,  # Store actual process.id
                )

                session.add(db_result)
                await session.commit()

                logger.debug(f"Saved alignment result {result_data['request_id']} to database")

        except Exception as e:
            logger.exception(f"Error saving alignment result to database: {str(e)}")

    async def close(self):
        """Cleanup resources"""
        # Stop any active alignments
        async with self._lock:
            for request_id in list(self.active_alignments.keys()):
                self.cancel_alignment(request_id)

        # Close hardware connections
        await self.motion_controller.close()
        await self.image_processor.close()

        logger.info("Alignment service closed")
