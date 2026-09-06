"""
Módulo de Seguridad, Autenticación e Identidades de SchemaCraft.
"""

from .dependencies import get_current_user, get_current_user_optional
from .models import (
    ProjectCollaboratorORM,
    ProjectORM,
    UserIdentityORM,
    UserORM,
    UserSessionORM,
)
from .router import router as auth_router

__all__ = [
    "ProjectCollaboratorORM",
    "ProjectORM",
    "UserIdentityORM",
    "UserORM",
    "UserSessionORM",
    "auth_router",
    "get_current_user",
    "get_current_user_optional",
]
