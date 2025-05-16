# OpenManufacturing Integrations Package

# This package is for integrating with third-party systems like ERPs, PLCs, specific vision systems etc.

# Example structure:
# from .erp.sap_connector import SAPConnector
# from .plc.siemens_s7_driver import S7Driver

import logging
logger = logging.getLogger(__name__)
logger.info("Integrations package initialized.")

# __all__ = ["SAPConnector", "S7Driver"] 