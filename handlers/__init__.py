from .admin import router as admin_router
from .errors import router as errors_router
from .user import router as user_router

__all__ = ["admin_router", "errors_router", "user_router"]
