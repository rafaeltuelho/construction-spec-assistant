"""FastAPI routers for the Construction Spec Assistant API."""

from .documents import router as documents_router
from .reviews import router as reviews_router
from .health import router as health_router

__all__ = [
    "documents_router",
    "reviews_router", 
    "health_router",
]
