# Core logic for OpenManufacturing platform

# This __init__.py can be used to make core components easily importable
# For example:
# from .alignment.alignment_engine import AlignmentEngine
# from .process.workflow_manager import WorkflowManager
# from .database.db import Base, get_session, init_db

import logging

logger = logging.getLogger(__name__)
logger.info("OpenManufacturing Core Package Initialized") 