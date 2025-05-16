from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    hashed_password = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))


class Batch(Base):
    """Production batch model"""

    __tablename__ = "batches"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    batch_type = Column(String(50))
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    status = Column(String(20), default="pending")
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    devices = relationship("Device", back_populates="batch")


class Device(Base):
    """Device model"""

    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    serial_number = Column(String(100), unique=True, index=True)
    name = Column(String(100))
    device_type = Column(String(50))
    description = Column(Text)
    specifications = Column(JSON)
    batch_id = Column(String(36), ForeignKey("batches.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    batch = relationship("Batch", back_populates="devices")
    alignment_results = relationship("AlignmentResult", back_populates="device")


class WorkflowTemplate(Base):
    """Workflow template model"""

    __tablename__ = "workflow_templates"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    version = Column(String(20))
    steps = Column(JSON, nullable=False)  # JSON array of workflow steps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    creator = relationship("User")
    process_instances = relationship("ProcessInstance", back_populates="template")


class ProcessInstance(Base):
    """Process instance model"""

    __tablename__ = "process_instances"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String(36), ForeignKey("workflow_templates.id"))
    batch_id = Column(String(36), ForeignKey("batches.id"))
    state = Column(String(20), default="PENDING")
    current_step_id = Column(String(36))
    step_results = Column(JSON)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    template = relationship("WorkflowTemplate", back_populates="process_instances")
    batch = relationship("Batch")
    alignment_results = relationship("AlignmentResult", back_populates="process")


class AlignmentResult(Base):
    """Alignment result model"""

    __tablename__ = "alignment_results"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"))
    process_id = Column(String(36), ForeignKey("process_instances.id"))
    success = Column(Boolean, default=False)
    optical_power_dbm = Column(Float)
    position_x = Column(Float)
    position_y = Column(Float)
    position_z = Column(Float)
    duration_ms = Column(Integer)
    iterations = Column(Integer)
    alignment_method = Column(String(50))
    error = Column(Text)
    metadata = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="alignment_results")
    process = relationship("ProcessInstance", back_populates="alignment_results")
