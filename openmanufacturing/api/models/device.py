"""
Device API models.

This module contains Pydantic models for device API endpoints.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    """Base device model with common fields"""
    name: str
    serial_number: str
    device_type: str
    description: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    batch_id: Optional[str] = None


class DeviceCreate(DeviceBase):
    """Device creation model"""
    id: Optional[str] = None  # Optional ID, will be auto-generated if not provided


class DeviceUpdate(BaseModel):
    """Device update model with all fields optional"""
    name: Optional[str] = None
    serial_number: Optional[str] = None
    device_type: Optional[str] = None
    description: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    batch_id: Optional[str] = None


class DeviceResponse(DeviceBase):
    """Device response model with all fields from database"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic config"""
        from_attributes = True  # Allows conversion from SQLAlchemy model
        from_orm = True  # For backward compatibility


class DeviceList(BaseModel):
    """List of devices with pagination information"""
    items: List[DeviceResponse]
    total: int
    skip: int
    limit: int 