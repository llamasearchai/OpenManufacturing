from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Assuming a DeviceService and Device model/dataclass exist in core
# from ...core.devices.service import DeviceService # Example path
# from ...core.devices.models import Device, DeviceCreate, DeviceUpdate # Example models

from ..dependencies import get_current_active_user # For authentication
from ..dependencies import User as PydanticUser # Pydantic user model

router = APIRouter()

# --- Mock Device Data and Service (Replace with actual service and DB interaction) --- #

mock_devices_db = {
    "dev-001": {"id": "dev-001", "name": "Alignment Stage Alpha", "type": "MotionController", "status": "online", "ip_address": "192.168.1.10"},
    "dev-002": {"id": "dev-002", "name": "Vision System Beta", "type": "Camera", "status": "offline", "ip_address": "192.168.1.11"},
    "dev-003": {"id": "dev-003", "name": "Power Meter Gamma", "type": "OpticalSensor", "status": "online", "ip_address": "192.168.1.12"},
}

class MockDeviceService:
    async def get_devices(self, skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        return list(mock_devices_db.values())[skip : skip + limit]

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        return mock_devices_db.get(device_id)

    async def create_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        dev_id = device_data.get("id", f"dev-{len(mock_devices_db) + 1:03d}")
        if dev_id in mock_devices_db:
            raise ValueError("Device ID already exists")
        new_device = device_data.copy()
        new_device["id"] = dev_id
        mock_devices_db[dev_id] = new_device
        return new_device

    async def update_device(self, device_id: str, device_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if device_id not in mock_devices_db:
            return None
        mock_devices_db[device_id].update(device_data)
        return mock_devices_db[device_id]

    async def delete_device(self, device_id: str) -> bool:
        if device_id in mock_devices_db:
            del mock_devices_db[device_id]
            return True
        return False

# Dependency to get the mock service instance
async def get_device_service(): # In a real app, this would come from a central registry or DI
    return MockDeviceService()

# --- Pydantic Models for Device API --- #

class DeviceBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    type: str = Field(..., description="Type of the device (e.g., MotionController, Camera, Sensor)")
    ip_address: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", description="IP address of the device")
    description: Optional[str] = None

class DeviceCreate(DeviceBase):
    id: Optional[str] = Field(None, description="Optional device ID, will be generated if not provided for some systems")

class DeviceUpdate(DeviceBase):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = Field(None, description="Device status (e.g., online, offline, error)")

class DeviceResponse(DeviceBase):
    id: str
    status: str = Field(..., description="Current status of the device")
    # Add other fields like last_seen, firmware_version etc. as needed

# --- API Endpoints --- #

@router.post("/", response_model=DeviceResponse, status_code=201, summary="Register a new device")
async def create_device(
    device_in: DeviceCreate,
    current_user: PydanticUser = Depends(get_current_active_user),
    device_service: MockDeviceService = Depends(get_device_service) # Replace with actual DeviceService
):
    try:
        created_device = await device_service.create_device(device_in.model_dump())
        return DeviceResponse(**created_device)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating device: {str(e)}")

@router.get("/", response_model=List[DeviceResponse], summary="List all registered devices")
async def list_devices(
    skip: int = 0,
    limit: int = 10,
    current_user: PydanticUser = Depends(get_current_active_user),
    device_service: MockDeviceService = Depends(get_device_service) # Replace with actual DeviceService
):
    devices = await device_service.get_devices(skip=skip, limit=limit)
    return [DeviceResponse(**dev) for dev in devices]

@router.get("/{device_id}", response_model=DeviceResponse, summary="Get details of a specific device")
async def get_device(
    device_id: str,
    current_user: PydanticUser = Depends(get_current_active_user),
    device_service: MockDeviceService = Depends(get_device_service) # Replace with actual DeviceService
):
    device = await device_service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse(**device)

@router.put("/{device_id}", response_model=DeviceResponse, summary="Update an existing device")
async def update_device(
    device_id: str,
    device_in: DeviceUpdate,
    current_user: PydanticUser = Depends(get_current_active_user),
    device_service: MockDeviceService = Depends(get_device_service) # Replace with actual DeviceService
):
    updated_device = await device_service.update_device(device_id, device_in.model_dump(exclude_unset=True))
    if not updated_device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse(**updated_device)

@router.delete("/{device_id}", status_code=204, summary="Delete a device")
async def delete_device(
    device_id: str,
    current_user: PydanticUser = Depends(get_current_active_user),
    device_service: MockDeviceService = Depends(get_device_service) # Replace with actual DeviceService
):
    success = await device_service.delete_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return # No content response for 204 