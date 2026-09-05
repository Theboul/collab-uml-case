"""
Endpoint de metadatos e información de la API v2.
"""


from fastapi import APIRouter

router = APIRouter(prefix="/api/v2", tags=["Info"])


@router.get("/info", summary="Información del servicio y versión de esquema UML")
def get_service_info() -> dict[str, str]:
    return {
        "service": "CASE Backend",
        "apiVersion": "2",
        "umlSchemaVersion": "2.0.0",
    }
