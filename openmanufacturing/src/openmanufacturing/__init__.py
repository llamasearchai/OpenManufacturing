# Initialize the OpenManufacturing Python package

__version__ = "1.0.0"

import logging

# Configure basic logging for the package
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler()) # Avoids "No handler found" warnings by default

def get_version():
    return __version__ 