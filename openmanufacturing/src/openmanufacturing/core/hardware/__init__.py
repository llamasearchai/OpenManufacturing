# OpenManufacturing Hardware Interface Package

# from .motion_controller import MotionController, SimulatedMotionController # Example
# from .camera_interface import Camera # Example
# from .sensor_interface import OpticalPowerMeter # Example

logger = logging.getLogger(__name__)
logger.info("Hardware package initialized.")

# __all__ = ["MotionController", "SimulatedMotionController", "Camera", "OpticalPowerMeter"]

import logging # Added import for logger to work 