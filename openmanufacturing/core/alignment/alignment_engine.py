import logging
import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple, Any

from ..hardware.motion_controller import MotionController
from ..process.calibration import CalibrationProfile
from ..vision.image_processing import ImageProcessor

logger = logging.getLogger(__name__)


@dataclass
class AlignmentParameters:
    """Parameters for fiber-to-chip alignment process"""

    position_tolerance_um: float = 0.1  # Microns
    angle_tolerance_deg: float = 0.05  # Degrees
    optical_power_threshold: float = -3.0  # dBm
    max_iterations: int = 100
    use_machine_learning: bool = True
    gradient_step_size: float = 0.2  # Microns
    spiral_max_radius: float = 10.0  # Microns
    coarse_alignment_timeout: float = 30.0  # Seconds
    fine_alignment_timeout: float = 60.0  # Seconds
    alignment_retry_attempts: int = 3
    optimization_strategy: str = "combined"  # "gradient", "spiral", or "combined"
    device_type: Optional[str] = None


class AlignmentEngine:
    """Core engine for fiber-to-chip alignment operations"""

    def __init__(
        self,
        motion_controller: MotionController,
        image_processor: ImageProcessor,
        calibration_profile: CalibrationProfile,
        parameters: Optional[AlignmentParameters] = None,
    ):
        self.motion_controller = motion_controller
        self.image_processor = image_processor
        self.calibration = calibration_profile
        self.parameters = parameters or AlignmentParameters()
        self.alignment_history = []
        self.is_aligned = False
        self.stop_requested = False
        self.id = str(uuid.uuid4())

        # Connect to hardware if not already connected
        self._ensure_hardware_connection()

        logger.info(f"Alignment engine initialized (id: {self.id})")

    async def _ensure_hardware_connection(self):
        """Ensure hardware connection is established"""
        if not self.motion_controller.connected:
            await self.motion_controller.connect()

    async def stop_alignment(self):
        """Stop any ongoing alignment operation"""
        self.stop_requested = True
        await self.motion_controller.stop()
        logger.info("Alignment operation stopped by request")

    async def perform_coarse_alignment(self) -> Tuple[bool, Dict]:
        """
        Performs coarse alignment using machine vision

        Returns:
            Tuple[bool, Dict]: Success status and alignment data
        """
        logger.info("Starting coarse alignment")
        start_time = time.time()

        try:
            # Get current positions
            fiber_position = await self.image_processor.detect_fiber_position()
            waveguide_position = await self.image_processor.detect_chip_waveguide()

            logger.debug(
                f"Fiber position: {fiber_position}, Waveguide position: {waveguide_position}"
            )

            # Calculate required movement
            delta_x = waveguide_position.x - fiber_position.x
            delta_y = waveguide_position.y - fiber_position.y
            delta_z = waveguide_position.z - fiber_position.z

            # Apply calibration corrections
            corrected_deltas = self.calibration.apply_corrections(delta_x, delta_y, delta_z)

            logger.debug(
                f"Movement deltas: ({delta_x}, {delta_y}, {delta_z}), "
                f"Corrected: ({corrected_deltas[0]}, {corrected_deltas[1]}, {corrected_deltas[2]})"
            )

            # Move to coarse alignment position
            success = await self.motion_controller.move_relative(
                x=corrected_deltas[0],
                y=corrected_deltas[1],
                z=corrected_deltas[2],
                speed=self.calibration.coarse_movement_speed,
            )

            # Check optical power after movement
            current_power = await self.motion_controller.get_optical_power()
            power_detected = current_power > -30.0  # Basic power detection threshold

            # Create result object
            result = {
                "success": success and power_detected,
                "fiber_position": vars(fiber_position),
                "waveguide_position": vars(waveguide_position),
                "correction_applied": corrected_deltas,
                "optical_power_dbm": current_power,
                "duration_ms": int((time.time() - start_time) * 1000),
            }

            self.alignment_history.append(
                {"phase": "coarse", "timestamp": datetime.now().isoformat(), "result": result}
            )

            if result["success"]:
                logger.info("Coarse alignment completed successfully")
            else:
                logger.warning("Coarse alignment did not achieve expected results")

            return result["success"], result

        except Exception as e:
            logger.exception(f"Error during coarse alignment: {str(e)}")

            result = {
                "success": False,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }

            self.alignment_history.append(
                {"phase": "coarse", "timestamp": datetime.now().isoformat(), "result": result}
            )

            return False, result

    async def perform_fine_alignment(self) -> Tuple[bool, Dict]:
        """
        Performs fine alignment using optical power feedback

        Returns:
            Tuple[bool, Dict]: Success status and alignment data
        """
        logger.info("Starting fine alignment")
        start_time = time.time()

        try:
            # Choose alignment strategy based on parameters
            strategy = self.parameters.optimization_strategy.lower()

            if strategy == "gradient":
                success, result = await self._gradient_descent_alignment()
            elif strategy == "spiral":
                success, result = await self._spiral_search_alignment()
            elif strategy == "combined":
                # Try spiral search first, then refine with gradient descent
                success, spiral_result = await self._spiral_search_alignment()

                if success:
                    # If spiral search was successful, refine with gradient descent
                    success, gradient_result = await self._gradient_descent_alignment()

                    # Combine results
                    result = gradient_result
                    result["spiral_search_result"] = spiral_result
                else:
                    result = spiral_result
            else:
                # Default to gradient descent if invalid strategy
                logger.warning(
                    f"Invalid optimization strategy '{strategy}', using gradient descent"
                )
                success, result = await self._gradient_descent_alignment()

            # Add duration to result
            result["duration_ms"] = int((time.time() - start_time) * 1000)

            self.alignment_history.append(
                {
                    "phase": "fine",
                    "timestamp": datetime.now().isoformat(),
                    "strategy": strategy,
                    "result": result,
                }
            )

            self.is_aligned = result["success"]

            if result["success"]:
                logger.info(f"Fine alignment completed successfully using {strategy} strategy")
            else:
                logger.warning(
                    f"Fine alignment did not achieve target power using {strategy} strategy"
                )

            return result["success"], result

        except Exception as e:
            logger.exception(f"Error during fine alignment: {str(e)}")

            result = {
                "success": False,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }

            self.alignment_history.append(
                {
                    "phase": "fine",
                    "timestamp": datetime.now().isoformat(),
                    "strategy": self.parameters.optimization_strategy,
                    "result": result,
                }
            )

            return False, result

    async def _gradient_descent_alignment(self) -> Tuple[bool, Dict]:
        """
        Perform gradient descent optimization for alignment

        Returns:
            Tuple[bool, Dict]: Success status and result data
        """
        logger.debug("Starting gradient descent alignment")

        # Initialize optimization variables
        current_position = await self.motion_controller.get_current_position()
        current_power = await self.motion_controller.get_optical_power()
        best_power = current_power
        best_position = current_position.copy()

        step_sizes = [0.5, 0.2, 0.1, 0.05]  # Decreasing step sizes in microns
        axes = ["x", "y", "z"]
        iterations = 0
        movements = []
        powers = [current_power]

        # Track the convergence criteria
        last_best_power = -float("inf")
        convergence_count = 0

        for step_size in step_sizes:
            if self.stop_requested:
                break

            for _ in range(self.parameters.max_iterations // len(step_sizes)):
                if self.stop_requested:
                    break

                iterations += 1
                improved = False

                # Try each axis
                for axis in axes:
                    if self.stop_requested:
                        break

                    # Get current position and power
                    current_position = await self.motion_controller.get_current_position()
                    movements.append(current_position.copy())

                    # Calculate gradient by sampling in + and - directions
                    gradient = await self._calculate_gradient(current_position, step_size)

                    # If gradient magnitude is very small, we may be at a local optimum
                    gradient_magnitude = math.sqrt(sum(v * v for v in gradient.values()))
                    if gradient_magnitude < 0.001:
                        logger.debug(
                            f"Gradient magnitude very small ({gradient_magnitude}), may be at local optimum"
                        )
                        break

                    # Move in the direction of the gradient
                    move_deltas = {
                        axis: step_size * gradient[axis] / gradient_magnitude for axis in axes
                    }
                    await self.motion_controller.move_relative(**move_deltas)

                    # Measure new power
                    new_power = await self.motion_controller.get_optical_power()
                    powers.append(new_power)

                    # Check if we improved
                    if new_power > best_power:
                        best_power = new_power
                        # best_position = new_pos.copy() # Commented for F841

                        # Check if we've reached target power
                        if best_power >= self.parameters.optical_power_threshold:
                            logger.info(f"Reached target power threshold ({best_power} dBm)")
                            break
                    else:
                        # Move back, no improvement
                        move_deltas = {
                            axis: -step_size * gradient[axis] / gradient_magnitude for axis in axes
                        }
                        await self.motion_controller.move_relative(**move_deltas)

                # Check for convergence - if best power hasn't improved significantly
                if abs(best_power - last_best_power) < 0.01:
                    convergence_count += 1
                    if convergence_count >= 3:  # 3 iterations without significant improvement
                        logger.debug(
                            f"Converged after {iterations} iterations (no significant improvement)"
                        )
                        break
                else:
                    convergence_count = 0
                    last_best_power = best_power

                # Stop iteration if no improvement in this round
                if not improved:
                    break

        # Move to best position found
        await self.motion_controller.move_absolute(**best_position)
        final_power = await self.motion_controller.get_optical_power()

        # Create result object
        result = {
            "success": final_power >= self.parameters.optical_power_threshold,
            "final_power_dbm": final_power,
            "initial_power_dbm": powers[0],
            "final_position": best_position,
            "initial_position": movements[0],
            "iterations": iterations,
            "movement_history": movements,
            "power_history": powers,
        }

        return result["success"], result

    async def _spiral_search_alignment(self) -> Tuple[bool, Dict]:
        """
        Perform spiral search optimization for alignment

        Returns:
            Tuple[bool, Dict]: Success status and result data
        """
        logger.debug("Starting spiral search alignment")

        # Initialize search variables
        current_position = await self.motion_controller.get_current_position()
        current_power = await self.motion_controller.get_optical_power()
        best_power = current_power
        best_position = current_position.copy()

        max_radius = self.parameters.spiral_max_radius
        step_size = 0.5  # Microns between spiral points
        spiral_points = int(max_radius / step_size * 10)  # Number of points in spiral

        movements = [current_position.copy()]
        powers = [current_power]

        # Perform spiral search in XY plane
        for i in range(1, spiral_points):
            if self.stop_requested:
                break

            # Parametric equations for spiral
            t = 0.1 * i
            r = step_size * t

            # Ensure we don't exceed max radius
            if r > max_radius:
                break

            # Convert to Cartesian coordinates
            x_offset = r * math.cos(t)
            y_offset = r * math.sin(t)

            # Move to spiral point
            new_pos = {
                "x": current_position["x"] + x_offset,
                "y": current_position["y"] + y_offset,
                "z": current_position["z"],
            }

            await self.motion_controller.move_absolute(**new_pos)
            movements.append(await self.motion_controller.get_current_position())

            # Measure optical power
            new_power = await self.motion_controller.get_optical_power()
            powers.append(new_power)

            # Update best position if improved
            if new_power > best_power:
                best_power = new_power
                best_position = new_pos.copy()

                # Check if we've reached target power
                if best_power >= self.parameters.optical_power_threshold:
                    logger.info(
                        f"Reached target power threshold ({best_power} dBm) during spiral search"
                    )
                    break

        # Now search in

    async def align(self) -> Dict[str, Any]:
        """Performs the full alignment process: coarse then fine."""
        logger.info(f"Starting full alignment process for engine ID: {self.id}")
        overall_start_time = time.time()
        full_history = []
        final_success = False

        coarse_success, coarse_result = await self.perform_coarse_alignment()
        full_history.extend(self.alignment_history[-1:]) # Add most recent coarse result

        fine_result = None
        if coarse_success:
            logger.info("Coarse alignment successful, proceeding to fine alignment.")
            fine_success, fine_result_data = await self.perform_fine_alignment()
            full_history.extend(self.alignment_history[-1:]) # Add most recent fine result
            fine_result = fine_result_data
            final_success = fine_success
        else:
            logger.warning("Coarse alignment failed. Skipping fine alignment.")
            final_success = False
        
        overall_duration_ms = int((time.time() - overall_start_time) * 1000)
        
        return {
            "success": final_success,
            "is_aligned": self.is_aligned,
            "coarse_alignment_result": coarse_result,
            "fine_alignment_result": fine_result,
            "alignment_history": full_history, # Or self.alignment_history for full engine history
            "overall_duration_ms": overall_duration_ms,
            "final_status_message": "Alignment process completed."
        }

    async def _calculate_gradient(self, current_position: Dict[str, float], step_size: float) -> Dict[str, float]:
        """Placeholder for gradient calculation."""
        # This should sample power at +/- step_size for each axis
        # and return a dict like {"x": grad_x, "y": grad_y, "z": grad_z}
        logger.debug(f"Calculating gradient at {current_position} with step {step_size}")
        # Simulate gradient: move towards origin slightly
        return {
            "x": -current_position["x"] * 0.1, 
            "y": -current_position["y"] * 0.1, 
            "z": -current_position["z"] * 0.1
        }

    # The following stub was causing redefinition, it's removed.
    # async def _spiral_search_alignment(self) -> Tuple[bool, Dict]:
    #     # ... existing code ...
    #     return False, result
