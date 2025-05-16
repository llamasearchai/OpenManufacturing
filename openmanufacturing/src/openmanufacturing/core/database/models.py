from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB # For PostgreSQL specific JSON type
from sqlalchemy.sql import func # For server-side default timestamps
import datetime

from .db import Base # Import Base from db.py within the same package

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Add relationships if needed, e.g., to ProcessInstance if user owns processes
    # process_instances = relationship("ProcessInstance", back_populates="owner")

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(String, primary_key=True, index=True) # Assuming UUID or string ID from example
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String, nullable=False, default="1.0.0")
    # Store steps as JSON. For complex queries on steps, a separate table might be better.
    steps_json = Column(JSONB, nullable=False, comment="JSON array of ProcessStep definitions") 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # created_by = relationship("User")

class ProcessInstance(Base):
    __tablename__ = "process_instances"

    id = Column(String, primary_key=True, index=True) # Assuming UUID or string ID
    template_id = Column(String, ForeignKey("workflow_templates.id"), nullable=False, index=True)
    batch_id = Column(String, index=True, nullable=True)
    state = Column(String, nullable=False, index=True) # Storing ProcessState enum name (e.g., "RUNNING")
    current_step_id = Column(String, nullable=True)
    
    # Store results and parameters as JSON. For complex queries, consider separate tables or specific JSON structures.
    step_results_json = Column(JSONB, nullable=True, comment="JSON object storing results of each step")
    parameters_json = Column(JSONB, nullable=True, comment="Initial parameters for this instance, if any")
    metadata = Column(JSONB, nullable=True, comment="Arbitrary metadata for this process instance")
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    template = relationship("WorkflowTemplate")
    # owner = relationship("User", back_populates="process_instances")

# You might also need models for Devices, AlignmentResults (if stored persistently beyond logs/cache), etc.

class Device(Base):
    __tablename__ = "devices"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=True, default="unknown")
    ip_address = Column(String, nullable=True)
    config_json = Column(JSONB, nullable=True, comment="Device specific configuration")
    description = Column(Text, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Example for storing detailed alignment results if needed beyond service memory cache
class AlignmentRun(Base):
    __tablename__ = "alignment_runs"
    id = Column(String, primary_key=True, index=True) # request_id from AlignmentService
    device_id = Column(String, ForeignKey("devices.id"), nullable=False, index=True)
    process_instance_id = Column(String, ForeignKey("process_instances.id"), nullable=True, index=True)
    success = Column(Boolean, nullable=False)
    optical_power_dbm = Column(Float, nullable=True)
    position_x = Column(Float, nullable=True)
    position_y = Column(Float, nullable=True)
    position_z = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    status = Column(String, nullable=False) # e.g. completed, failed, cancelled
    alignment_parameters_json = Column(JSONB, nullable=True)
    trajectory_json = Column(JSONB, nullable=True) # Could be large
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    device = relationship("Device")
    process_instance = relationship("ProcessInstance") 