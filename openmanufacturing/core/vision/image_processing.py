import json
import logging
import math
import os
import random
from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Position3D:
    """3D position with confidence"""

    x: float
    y: float
    z: float
    confidence: float = 1.0


class ImageProcessor:
    """Processes images for fiber and chip detection"""

    def __init__(
        self,
        camera_id: str = "default",
        config_path: str = "config/vision.json",
        simulation_mode: bool = False,
    ):
        """
        Initialize image processor

        Args:
            camera_id: Camera identifier
            config_path: Path to vision configuration file
            simulation_mode: Whether to simulate camera input
        """
        self.camera_id = camera_id
        self.config_path = config_path
        self.simulation_mode = simulation_mode

        # Load configuration if file exists
        self.config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    self.config = json.load(f)
                logger.info(f"Loaded vision configuration from {config_path}")
            except Exception as e:
                logger.error(f"Failed to load vision configuration: {str(e)}")

        # Default parameters
        self.default_params = {
            "fiber_detection": {
                "blur_kernel": 5,
                "canny_low": 50,
                "canny_high": 150,
                "hough_threshold": 50,
                "min_line_length": 50,
                "max_line_gap": 10,
            },
            "waveguide_detection": {
                "blur_kernel": 5,
                "threshold": 180,
                "min_area": 10,
                "max_area": 500,
            },
        }

        # Initialize cameras
        self.top_camera = None
        self.side_camera = None

        if not simulation_mode:
            try:
                # Initialize real cameras
                # This would open actual camera connections
                # self.top_camera = cv2.VideoCapture(camera_id_top)
                # self.side_camera = cv2.VideoCapture(camera_id_side)
                pass
            except Exception as e:
                logger.error(f"Failed to initialize cameras: {str(e)}")
                # Fall back to simulation mode
                self.simulation_mode = True

        logger.info(f"Image processor initialized (simulation: {self.simulation_mode})")

    async def capture_images(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Capture top and side images

        Returns:
            Tuple of (top_image, side_image) as numpy arrays
        """
        if self.simulation_mode:
            # Generate simulated images
            top_image = np.zeros((480, 640, 3), dtype=np.uint8)
            side_image = np.zeros((480, 640, 3), dtype=np.uint8)

            # Draw simulated fiber
            fiber_x = 320 + random.randint(-5, 5)
            fiber_y = 240 + random.randint(-5, 5)
            fiber_z = 240 + random.randint(-5, 5)

            # Top view - fiber appears as a line
            cv2.line(
                top_image, (fiber_x - 100, fiber_y), (fiber_x + 100, fiber_y), (200, 200, 200), 2
            )
            # Add bright spot at the tip
            cv2.circle(top_image, (fiber_x, fiber_y), 5, (250, 250, 250), -1)

            # Side view - fiber appears as a horizontal line
            cv2.line(
                side_image, (fiber_x - 100, fiber_z), (fiber_x + 100, fiber_z), (200, 200, 200), 2
            )
            # Add bright spot at the tip
            cv2.circle(side_image, (fiber_x, fiber_z), 5, (250, 250, 250), -1)

            # Draw simulated chip
            chip_x = 320 + random.randint(-20, 20)
            chip_y = 240 + random.randint(-20, 20)
            chip_z = 240 + random.randint(-20, 20)

            # Top view - chip outline
            cv2.rectangle(
                top_image,
                (chip_x - 150, chip_y - 100),
                (chip_x + 150, chip_y + 100),
                (150, 150, 150),
                2,
            )
            # Side view - chip outline
            cv2.rectangle(
                side_image,
                (chip_x - 150, chip_z - 20),
                (chip_x + 150, chip_z + 20),
                (150, 150, 150),
                2,
            )

            # Add simulated waveguide
            waveguide_x = chip_x + 150  # Right edge of chip
            waveguide_y = chip_y
            waveguide_z = chip_z

            # Top view - waveguide
            cv2.circle(top_image, (waveguide_x, waveguide_y), 3, (255, 255, 255), -1)
            # Side view - waveguide
            cv2.circle(side_image, (waveguide_x, waveguide_z), 3, (255, 255, 255), -1)

            # Add some noise
            noise = np.random.normal(0, 10, top_image.shape).astype(np.int8)
            top_image = cv2.add(top_image, noise)

            noise = np.random.normal(0, 10, side_image.shape).astype(np.int8)
            side_image = cv2.add(side_image, noise)

            logger.debug("Captured simulated images")
            return top_image, side_image

        else:
            # Capture from real cameras
            try:
                # This would capture from actual cameras
                # ret_top, top_frame = self.top_camera.read()
                # ret_side, side_frame = self.side_camera.read()
                # return top_frame, side_frame

                # Placeholder for now
                logger.warning("Real camera capture not implemented, using simulated images")
                return await self.capture_images()

            except Exception as e:
                logger.error(f"Failed to capture from cameras: {str(e)}")
                # Fall back to simulation
                self.simulation_mode = True
                return await self.capture_images()

    async def detect_fiber_position(self) -> Position3D:
        """
        Detect fiber position from top and side images

        Returns:
            3D position of fiber tip
        """
        # Capture images
        top_image, side_image = await self.capture_images()

        # Get parameters
        params = self.config.get("fiber_detection", self.default_params["fiber_detection"])

        # Convert to grayscale
        gray_top = cv2.cvtColor(top_image, cv2.COLOR_BGR2GRAY)
        gray_side = cv2.cvtColor(side_image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur
        blur_kernel = params["blur_kernel"]
        blur_top = cv2.GaussianBlur(gray_top, (blur_kernel, blur_kernel), 0)
        blur_side = cv2.GaussianBlur(gray_side, (blur_kernel, blur_kernel), 0)

        # Edge detection
        canny_low = params["canny_low"]
        canny_high = params["canny_high"]
        edges_top = cv2.Canny(blur_top, canny_low, canny_high)
        edges_side = cv2.Canny(blur_side, canny_low, canny_high)

        # Hough line detection
        hough_threshold = params["hough_threshold"]
        min_line_length = params["min_line_length"]
        max_line_gap = params["max_line_gap"]

        lines_top = cv2.HoughLinesP(
            edges_top,
            1,
            np.pi / 180,
            hough_threshold,
            minLineLength=min_line_length,
            maxLineGap=max_line_gap,
        )

        lines_side = cv2.HoughLinesP(
            edges_side,
            1,
            np.pi / 180,
            hough_threshold,
            minLineLength=min_line_length,
            maxLineGap=max_line_gap,
        )

        # Find fiber in top view (typically the longest horizontal line)
        top_x, top_y = 0, 0
        top_confidence = 0.0

        if lines_top is not None:
            max_length = 0
            best_line = None

            for line in lines_top:
                x1, y1, x2, y2 = line[0]
                # Calculate line length
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                # Check if line is mostly horizontal
                angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
                if (angle < 10 or angle > 170) and length > max_length:
                    max_length = length
                    best_line = line[0]

            if best_line is not None:
                x1, y1, x2, y2 = best_line
                # Get coordinates of rightmost tip (fiber tip)
                if x1 > x2:
                    top_x, top_y = x1, y1
                else:
                    top_x, top_y = x2, y2

                # Confidence based on line length
                top_confidence = min(1.0, max_length / 200)

        # Find fiber in side view
        side_x, side_z = 0, 0
        side_confidence = 0.0

        if lines_side is not None:
            max_length = 0
            best_line = None

            for line in lines_side:
                x1, y1, x2, y2 = line[0]
                # Calculate line length
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                # Check if line is mostly horizontal
                angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
                if (angle < 10 or angle > 170) and length > max_length:
                    max_length = length
                    best_line = line[0]

            if best_line is not None:
                x1, y1, x2, y2 = best_line
                # Get coordinates of rightmost tip (fiber tip)
                if x1 > x2:
                    side_x, side_z = x1, y1
                else:
                    # side_x, side_z = x2, y2 # Commented for F841
                    _, side_z = x2, y2  # Assign only side_z if side_x is unused

                # Confidence based on line length
                side_confidence = min(1.0, max_length / 200)

        # If line detection failed, try finding the brightest spot
        if top_confidence == 0:
            # Find brightest spot in right half of image (fiber tip is typically bright)
            right_half = gray_top[:, gray_top.shape[1] // 2 :]
            _, max_val, _, max_loc = cv2.minMaxLoc(right_half)

            if max_val > 200:  # If there's a bright spot
                top_x = max_loc[0] + gray_top.shape[1] // 2  # Adjust for right half offset
                top_y = max_loc[1]
                top_confidence = 0.5

        if side_confidence == 0:
            # Find brightest spot in right half of image
            right_half = gray_side[:, gray_side.shape[1] // 2 :]
            _, max_val, _, max_loc = cv2.minMaxLoc(right_half)

            # If there's a bright spot, consider it a feature
            if max_val > 200:  # If there's a bright spot
                # side_x = max_loc[0] + gray_side.shape[1] // 2  # Adjust for right half offset # Temporarily commented for ruff F841
                side_z = max_loc[1]
                side_confidence = 0.5

        # Convert pixel coordinates to world coordinates
        # This would need calibration information to be accurate
        # Here we just use a simple scaling factor
        scale_factor = 0.1  # microns per pixel

        x = top_x * scale_factor
        y = top_y * scale_factor
        z = side_z * scale_factor

        # Average confidence
        confidence = (top_confidence + side_confidence) / 2

        logger.debug(f"Detected fiber position: ({x}, {y}, {z}) with confidence {confidence:.2f}")
        return Position3D(x=x, y=y, z=z, confidence=confidence)

    async def detect_chip_waveguide(self) -> Position3D:
        """
        Detect waveguide position on chip

        Returns:
            3D position of waveguide
        """
        # Capture images
        top_image, side_image = await self.capture_images()

        # Get parameters
        params = self.config.get("waveguide_detection", self.default_params["waveguide_detection"])

        # Convert to grayscale
        gray_top = cv2.cvtColor(top_image, cv2.COLOR_BGR2GRAY)
        gray_side = cv2.cvtColor(side_image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur
        blur_kernel = params["blur_kernel"]
        blur_top = cv2.GaussianBlur(gray_top, (blur_kernel, blur_kernel), 0)
        blur_side = cv2.GaussianBlur(gray_side, (blur_kernel, blur_kernel), 0)

        # Threshold to find bright spots (waveguides)
        threshold = params["threshold"]
        _, thresh_top = cv2.threshold(blur_top, threshold, 255, cv2.THRESH_BINARY)
        _, thresh_side = cv2.threshold(blur_side, threshold, 255, cv2.THRESH_BINARY)

        # Find contours
        contours_top, _ = cv2.findContours(thresh_top, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_side, _ = cv2.findContours(thresh_side, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contours by area
        min_area = params["min_area"]
        max_area = params["max_area"]

        # Find waveguide in top view
        top_x, top_y = 0, 0
        top_confidence = 0.0
        max_intensity = 0

        for contour in contours_top:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Check if contour is approximately square (waveguide spot)
                aspect_ratio = float(w) / h if h > 0 else 0
                if 0.5 <= aspect_ratio <= 2.0:
                    # Check average intensity in this region
                    roi = gray_top[y : y + h, x : x + w]
                    avg_intensity = np.mean(roi)

                    if avg_intensity > max_intensity:
                        max_intensity = avg_intensity
                        top_x = x + w // 2
                        top_y = y + h // 2
                        top_confidence = min(1.0, avg_intensity / 255)

        # Find waveguide in side view
        side_x, side_z = 0, 0
        side_confidence = 0.0
        max_intensity = 0

        for contour in contours_side:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Check if contour is approximately square (waveguide spot)
                aspect_ratio = float(w) / h if h > 0 else 0
                if 0.5 <= aspect_ratio <= 2.0:
                    # Check average intensity in this region
                    roi = gray_side[y : y + h, x : x + w]
                    avg_intensity = np.mean(roi)

                    if avg_intensity > max_intensity:
                        max_intensity = avg_intensity
                        # side_x = x + w // 2 # Commented for F841
                        side_z = y + h // 2
                        side_confidence = min(1.0, avg_intensity / 255)

        # If contour detection failed, try finding the brightest spot
        if top_confidence == 0:
            # Find brightest spot
            _, max_val, _, max_loc = cv2.minMaxLoc(gray_top)

            if max_val > 200:  # If there's a bright spot
                top_x = max_loc[0]
                top_y = max_loc[1]
                top_confidence = 0.5

        if side_confidence == 0:
            # Find brightest spot
            _, max_val, _, max_loc = cv2.minMaxLoc(gray_side)

            # If there's a bright spot, consider it a feature
            if max_val > 200:  # If there's a bright spot
                # side_x = max_loc[0] + gray_side.shape[1] // 2  # Adjust for right half offset # Temporarily commented for ruff F841
                side_z = max_loc[1]
                side_confidence = 0.5

        # Convert pixel coordinates to world coordinates
        # This would need calibration information to be accurate
        # Here we just use a simple scaling factor
        scale_factor = 0.1  # microns per pixel

        x = top_x * scale_factor
        y = top_y * scale_factor
        z = side_z * scale_factor

        # Average confidence
        confidence = (top_confidence + side_confidence) / 2

        logger.debug(
            f"Detected waveguide position: ({x}, {y}, {z}) with confidence {confidence:.2f}"
        )
        return Position3D(x=x, y=y, z=z, confidence=confidence)

    async def close(self):
        """Close camera connections"""
        if not self.simulation_mode:
            # Close real camera connections
            if self.top_camera:
                self.top_camera.release()
            if self.side_camera:
                self.side_camera.release()

        logger.info("Image processor closed")
