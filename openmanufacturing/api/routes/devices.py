from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import uuid

from ..dependencies import get_db, get_current_active_user
from ..models.device import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceList
from ...core.database.models import Device, Batch, AlignmentResult, User

router = APIRouter(prefix="/api/devices", tags=["devices"])

@router.post("/", response_model=DeviceResponse)
async def create_device(
    device: DeviceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new device"""
    # Check if batch exists if provided
    if device.batch_id:
        batch = await session.get(Batch, device.batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
    
    # Generate ID if not provided
    device_id = device.id or str(uuid.uuid4())
    
    # Create new device
    db_device = Device(
        id=device_id,
        serial_number=device.serial_number,
        name=device.name,
        device_type=device.device_type,
        description=device.description,
        specifications=device.specifications,
        batch_id=device.batch_id
    )
    
    session.add(db_device)
    await session.commit()
    await session.refresh(db_device)
    
    return DeviceResponse.from_orm(db_device)

@router.get("/", response_model=DeviceList)
async def list_devices(
    batch_id: Optional[str] = None,
    device_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List devices with optional filtering"""
    # Build query
    query = select(Device)
    
    # Apply filters
    if batch_id:
        query = query.where(Device.batch_id == batch_id)
    if device_type:
        query = query.where(Device.device_type == device_type)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    devices = result.scalars().all()
    
    return DeviceList(
        items=[DeviceResponse.from_orm(d) for d in devices],
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get device by ID"""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return DeviceResponse.from_orm(device)

@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_update: DeviceUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update device"""
    # Get existing device
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Check if batch exists if changing
    if device_update.batch_id is not None and device_update.batch_id != device.batch_id:
        if device_update.batch_id:  # Only check if not None
            batch = await session.get(Batch, device_update.batch_id)
            if not batch:
                raise HTTPException(status_code=404, detail="Batch not found")
    
    # Update fields
    update_data = device_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)
    
    # Update timestamp
    device.updated_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(device)
    
    return DeviceResponse.from_orm(device)

@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete device"""
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Check if device has alignment results
    alignment_query = select(func.count()).select_from(AlignmentResult).where(
        AlignmentResult.device_id == device_id
    )
    alignment_count = await session.scalar(alignment_query)
    
    if alignment_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete device with {alignment_count} alignment results"
        )
    
    await session.delete(device)
    await session.commit()