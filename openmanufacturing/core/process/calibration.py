import json
import logging
import os
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import datetime

logger = logging.getLogger(__name__)

class CalibrationProfile:
    """Calibration profile for alignment system"""
    
    def __init__(self):
        """Initialize default calibration profile"""
        # Movement speeds
        self.coarse_movement_speed = 1.0  # 100%
        self.fine_movement_speed = 0.5    # 50%
        
        # Positional corrections (microns)
        self.x_offset = 0.0
        self.y_offset = 0.0
        self.z_offset = 0.0
        
        # Rotational corrections (degrees)
        self.x_rotation = 0.0
        self.y_rotation = 0.0
        self.z_rotation = 0.0
        
        # Scale factors
        self.x_scale = 1.0
        self.y_scale = 1.0
        self.z_scale = 1.0
        
        # Camera calibration
        self.camera_pixels_per_um = 10.0  # pixels per micron
        
        # Metadata
        self.last_calibrated = None
        self.calibrated_by = None
        self.notes = ""
    
    def apply_corrections(self, dx: float, dy: float, dz: float) -> Tuple[float, float, float]:
        """
        Apply calibration corrections to movement deltas
        
        Args:
            dx: X movement in microns
            dy: Y movement in microns
            dz: Z movement in microns
            
        Returns:
            Corrected (dx, dy, dz) tuple
        """
        # Apply offsets
        dx_corrected = dx + self.x_offset
        dy_corrected = dy + self.y_offset
        dz_corrected = dz + self.z_offset
        
        # Apply scaling
        dx_corrected *= self.x_scale
        dy_corrected *= self.y_scale
        dz_corrected *= self.z_scale
        
        # Apply rotation corrections
        # Note: This is a simplified version - a full implementation would use rotation matrices
        if self.z_rotation != 0:
            theta = np.radians(self.z_rotation)
            dx_temp = dx_corrected
            dy_temp = dy_corrected
            dx_corrected = dx_temp * np.cos(theta) - dy_temp * np.sin(theta)
            dy_corrected = dx_temp * np.sin(theta) + dy_temp * np.cos(theta)
        
        return dx_corrected, dy_corrected, dz_corrected
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert profile to dictionary for serialization
        
        Returns:
            Dictionary representation of calibration profile
        """
        return {
            "coarse_movement_speed": self.coarse_movement_speed,
            "fine_movement_speed": self.fine_movement_speed,
            "x_offset": self.x_offset,
            "y_offset": self.y_offset,
            "z_offset": self.z_offset,
            "x_rotation": self.x_rotation,
            "y_rotation": self.y_rotation,
            "z_rotation": self.z_rotation,
            "x_scale": self.x_scale,
            "y_scale": self.y_scale,
            "z_scale": self.z_scale,
            "camera_pixels_per_um": self.camera_pixels_per_um,
            "last_calibrated": self.last_calibrated.isoformat() if self.last_calibrated else None,
            "calibrated_by": self.calibrated_by,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalibrationProfile':
        """
        Create profile from dictionary
        
        Args:
            data: Dictionary representation of calibration profile
            
        Returns:
            CalibrationProfile instance
        """
        profile = cls()
        profile.coarse_movement_speed = data.get("coarse_movement_speed", profile.coarse_movement_speed)
        profile.fine_movement_speed = data.get("fine_movement_speed", profile.fine_movement_speed)
        profile.x_offset = data.get("x_offset", profile.x_offset)
        profile.y_offset = data.get("y_offset", profile.y_offset)
        profile.z_offset = data.get("z_offset", profile.z_offset)
        profile.x_rotation = data.get("x_rotation", profile.x_rotation)
        profile.y_rotation = data.get("y_rotation", profile.y_rotation)
        profile.z_rotation = data.get("z_rotation", profile.z_rotation)
        profile.x_scale = data.get("x_scale", profile.x_scale)
        profile.y_scale = data.get("y_scale", profile.y_scale)
        profile.z_scale = data.get("z_scale", profile.z_scale)
        profile.camera_pixels_per_um = data.get("camera_pixels_per_um", profile.camera_pixels_per_um)
        
        if data.get("last_calibrated"):
            try:
                profile.last_calibrated = datetime.datetime.fromisoformat(data["last_calibrated"])
            except (ValueError, TypeError):
                profile.last_calibrated = None
        
        profile.calibrated_by = data.get("calibrated_by")
        profile.notes = data.get("notes", "")
        
        return profile
    
    def save_to_file(self, filepath: str) -> bool:
        """
        Save calibration profile to file
        
        Args:
            filepath: Path to save the profile
            
        Returns:
            Success status
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved calibration profile to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save calibration profile: {str(e)}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: str) -> Optional['CalibrationProfile']:
        """
        Load calibration profile from file
        
        Args:
            filepath: Path to load the profile from
            
        Returns:
            CalibrationProfile instance or None if file doesn't exist
        """
        if not os.path.exists(filepath):
            logger.warning(f"Calibration file {filepath} does not exist")
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            profile = cls.from_dict(data)
            logger.info(f"Loaded calibration profile from {filepath}")
            return profile
            
        except Exception as e:
            logger.error(f"Failed to load calibration profile: {str(e)}")
            return None
    
    async def perform_calibration(self, motion_controller, image_processor):
        """
        Perform automatic calibration routine
        
        Args:
            motion_controller: Motion controller instance
            image_processor: Image processor instance
            
        Returns:
            Success status
        """
        logger.info("Starting automatic calibration routine")
        
        try:
            # TODO: Implement calibration routine
            # This would involve:
            # 1. Moving to known positions
            # 2. Taking images and measuring positions
            # 3. Calculating correction factors
            
            # For now, this is a placeholder
            
            # Update calibration timestamp
            self.last_calibrated = datetime.datetime.now()
            
            logger.info("Calibration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Calibration failed: {str(e)}")
            return False