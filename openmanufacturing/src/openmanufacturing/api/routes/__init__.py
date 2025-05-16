# Routes for the OpenManufacturing API

from fastapi import APIRouter

# Import individual route modules here to make them available under this package
from . import alignment
from . import process
from . import auth
from . import devices
from . import workflow

# You can define a main router here if you want to aggregate all of them,
# or they can be individually included in the main FastAPI app.

# Example of an aggregated router (optional):
# aggregated_router = APIRouter()
# aggregated_router.include_router(alignment.router, prefix="/alignment", tags=["Alignment"])
# aggregated_router.include_router(process.router, prefix="/process", tags=["Process"])
# ... and so on 