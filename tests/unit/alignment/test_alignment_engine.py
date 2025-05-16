import asyncio  # Added for asyncio.create_task and sleep
from unittest.mock import AsyncMock, MagicMock, patch  # Use AsyncMock for async methods

import numpy as np
import pytest

# Assuming the new structure: openmanufacturing/src/openmanufacturing/core/...
from openmanufacturing.core.alignment.alignment_engine import (
    AlignmentEngine,
    AlignmentParameters,
)
from openmanufacturing.core.alignment.alignment_engine import (
    MockPosition as CoreMockPosition,  # If MockPosition is from engine
)
from openmanufacturing.core.process.calibration import CalibrationProfile

# The test defines its own MockMotionController, which is fine for isolating tests.
# If a real one exists, it might be type hinted, but the mock is used for injection.
# from openmanufacturing.core.hardware.motion_controller import MotionController as ActualMotionController

# Re-define or import necessary mock components if they are not part of the core modules being tested
# For this test, it seems MockMotionController is defined locally.
# Vision functions are patched.


@pytest.fixture
def mock_motion_controller():
    mock = AsyncMock()  # Use AsyncMock for an async interface

    current_position_state = {"x": 1.0, "y": 1.0, "z": 1.0}
    optical_power_state = {"power": -10.0}  # Initial power

    async def move_relative(x=0, y=0, z=0, speed=None):
        current_position_state["x"] += x
        current_position_state["y"] += y
        current_position_state["z"] += z
        # Simulate power change based on proximity to an optimal point (e.g., 0,0,0 for fine alignment tests)
        dist_sq = (
            current_position_state["x"] ** 2
            + current_position_state["y"] ** 2
            + current_position_state["z"] ** 2
        )
        optical_power_state["power"] = (
            -2.0 * np.exp(-dist_sq / 2.0) - 1.0
        )  # Peak at -1dBm at (0,0,0)
        return True

    async def move_absolute(x=None, y=None, z=None, speed=None):
        if x is not None:
            current_position_state["x"] = x
        if y is not None:
            current_position_state["y"] = y
        if z is not None:
            current_position_state["z"] = z
        dist_sq = (
            current_position_state["x"] ** 2
            + current_position_state["y"] ** 2
            + current_position_state["z"] ** 2
        )
        optical_power_state["power"] = -2.0 * np.exp(-dist_sq / 2.0) - 1.0
        return True

    async def get_optical_power():
        return optical_power_state["power"]

    async def get_current_position():
        return current_position_state.copy()

    mock.move_relative = AsyncMock(side_effect=move_relative)
    mock.move_absolute = AsyncMock(side_effect=move_absolute)
    mock.get_optical_power = AsyncMock(side_effect=get_optical_power)
    mock.get_current_position = AsyncMock(side_effect=get_current_position)
    mock.initialize = AsyncMock()  # Add mock for initialize if engine calls it
    mock.close = AsyncMock()

    return mock


@pytest.fixture
def mock_calibration_profile():
    profile = MagicMock(spec=CalibrationProfile)
    profile.coarse_movement_speed = 100.0
    profile.fine_movement_step = 0.1
    # Make apply_corrections simply return the deltas for testing purposes
    profile.apply_corrections = MagicMock(side_effect=lambda dx, dy, dz: (dx, dy, dz))
    return profile


@pytest.fixture
def alignment_engine(mock_motion_controller, mock_calibration_profile):
    # Parameters as defined in the main.txt example for AlignmentEngine tests
    params = AlignmentParameters(
        position_tolerance_um=0.1,
        angle_tolerance_deg=0.05,
        optical_power_threshold=-3.0,  # dBm
        max_iterations=50,  # Reduced for faster tests from default 100
        fine_step_sizes_um=[0.5, 0.1, 0.05],  # Simplified for testing
    )
    engine = AlignmentEngine(
        motion_controller=mock_motion_controller,
        calibration_profile=mock_calibration_profile,
        parameters=params,
    )
    return engine


# Path for patching vision functions based on the new structure
VISION_PROCESSING_PATH = "openmanufacturing.core.alignment.alignment_engine"  # Patches where detect_fiber_position is *called from*


@pytest.mark.asyncio
async def test_coarse_alignment(alignment_engine, mock_motion_controller, mock_calibration_profile):
    mock_detect_fiber_patcher = patch(
        f"{VISION_PROCESSING_PATH}.detect_fiber_position", new_callable=AsyncMock
    )
    mock_detect_waveguide_patcher = patch(
        f"{VISION_PROCESSING_PATH}.detect_chip_waveguide", new_callable=AsyncMock
    )

    with (
        mock_detect_fiber_patcher as mock_detect_fiber,
        mock_detect_waveguide_patcher as mock_detect_waveguide,
    ):

        # Setup mock return values for vision
        # Using CoreMockPosition (or a similar structure) as defined in alignment_engine or a common types file
        mock_detect_fiber.return_value = CoreMockPosition(x=10.0, y=10.0, z=1.0)
        mock_detect_waveguide.return_value = CoreMockPosition(x=0.0, y=0.0, z=0.0)

        # Ensure initial position of mock_motion_controller is known if relevant before call
        # (The mock_motion_controller fixture sets an initial state)

        success, result = await alignment_engine.perform_coarse_alignment()

        assert success is True
        assert "initial_fiber_position" in result
        assert "initial_waveguide_position" in result
        assert "corrected_deltas_applied" in result

        # Check that move_relative was called on the motion controller
        mock_motion_controller.move_relative.assert_called_once()
        # Expected movement: from (10,10,1) towards (0,0,0) -> dx=-10, dy=-10, dz=-1
        # apply_corrections is mocked to pass through, so these are the deltas
        call_args = mock_motion_controller.move_relative.call_args[1]  # Get kwargs
        assert call_args["x"] == -10.0
        assert call_args["y"] == -10.0
        assert call_args["z"] == -1.0
        assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_fine_alignment_success(alignment_engine, mock_motion_controller):
    # Set initial position of mock controller somewhat away from optimum (0,0,0 based on mock power simulation)
    await mock_motion_controller.move_absolute(x=0.8, y=-0.7, z=0.3)
    initial_power = await mock_motion_controller.get_optical_power()

    success, result = await alignment_engine.perform_fine_alignment()

    assert success is True
    assert result["final_power_dbm"] >= alignment_engine.parameters.optical_power_threshold
    # Check that the final position is close to the optimal (0,0,0 in this mock power model)
    assert (
        abs(result["final_position"]["x"]) < alignment_engine.parameters.position_tolerance_um * 2
    )  # Allow some margin
    assert (
        abs(result["final_position"]["y"]) < alignment_engine.parameters.position_tolerance_um * 2
    )
    assert (
        abs(result["final_position"]["z"]) < alignment_engine.parameters.position_tolerance_um * 2
    )
    assert result["final_power_dbm"] > initial_power  # Power should have improved
    assert result["iterations_performed"] > 0
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_full_alignment_process(
    alignment_engine, mock_motion_controller, mock_calibration_profile
):
    mock_detect_fiber_patcher = patch(
        f"{VISION_PROCESSING_PATH}.detect_fiber_position", new_callable=AsyncMock
    )
    mock_detect_waveguide_patcher = patch(
        f"{VISION_PROCESSING_PATH}.detect_chip_waveguide", new_callable=AsyncMock
    )

    with (
        mock_detect_fiber_patcher as mock_detect_fiber,
        mock_detect_waveguide_patcher as mock_detect_waveguide,
    ):

        mock_detect_fiber.return_value = CoreMockPosition(x=5.0, y=-5.0, z=0.5)
        mock_detect_waveguide.return_value = CoreMockPosition(x=0.1, y=0.1, z=0.1)

        # Set initial controller position (will be overridden by coarse alignment effectively)
        await mock_motion_controller.move_absolute(x=6.0, y=-4.0, z=1.0)

        full_result = await alignment_engine.align()

        assert full_result["success"] is True
        assert full_result["is_aligned"] is True
        assert "coarse_alignment_result" in full_result
        assert "fine_alignment_result" in full_result
        assert full_result["coarse_alignment_result"]["success"] is True
        assert full_result["fine_alignment_result"]["success"] is True
        assert len(full_result["alignment_history"]) >= 2  # Coarse and Fine phases

        fine_res = full_result["fine_alignment_result"]
        assert fine_res["final_power_dbm"] >= alignment_engine.parameters.optical_power_threshold
        assert (
            abs(fine_res["final_position"]["x"])
            < alignment_engine.parameters.position_tolerance_um * 2
        )
        assert (
            abs(fine_res["final_position"]["y"])
            < alignment_engine.parameters.position_tolerance_um * 2
        )
        assert (
            abs(fine_res["final_position"]["z"])
            < alignment_engine.parameters.position_tolerance_um * 2
        )
        assert full_result["overall_duration_ms"] > 0


@pytest.mark.asyncio
async def test_alignment_stop_request(alignment_engine, mock_motion_controller):
    # This test needs to ensure the stop flag is checked.
    # The mock AlignmentEngine uses an internal _stop_alignment_flag.
    # We call request_stop_alignment() and then run a phase.

    mock_detect_fiber_patcher = patch(
        f"{VISION_PROCESSING_PATH}.detect_fiber_position", new_callable=AsyncMock
    )
    mock_detect_waveguide_patcher = patch(
        f"{VISION_PROCESSING_PATH}.detect_chip_waveguide", new_callable=AsyncMock
    )

    with (
        mock_detect_fiber_patcher as mock_detect_fiber,
        mock_detect_waveguide_patcher as mock_detect_waveguide,
    ):
        mock_detect_fiber.return_value = CoreMockPosition(x=1.0, y=1.0, z=1.0)
        mock_detect_waveguide.return_value = CoreMockPosition(x=0.0, y=0.0, z=0.0)

        # Start alignment in a task, then request stop
        alignment_task = asyncio.create_task(alignment_engine.align())

        await asyncio.sleep(0.01)  # Give a moment for alignment to potentially start a step
        alignment_engine.request_stop_alignment()

        result = await alignment_task

        assert result["success"] is False
        assert result["cancelled"] is True
        assert (
            "stopped" in result["final_status_message"].lower()
            or "cancelled" in result["final_status_message"].lower()
        )
