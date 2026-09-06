"""
Manejadores globales de excepciones para traducir errores del dominio UML
al formato canónico de error de la API (definido en AGENTS.md sección 7).
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from core.uml_domain.exceptions import (
    CanvasNoEncontrado,
    ConcurrentEditConflict,
    ElementoNoEncontrado,
    UmlDomainError,
    UmlValidationError,
    UnsupportedGenerationFeature,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            content = {
                "code": exc.detail.get("code", f"HTTP_{exc.status_code}"),
                "message": exc.detail.get("message", "Error en la solicitud."),
                "details": exc.detail.get("details", []),
            }
            return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": [],
            },
            headers=exc.headers,
        )

    @app.exception_handler(CanvasNoEncontrado)
    async def canvas_not_found_handler(request: Request, exc: CanvasNoEncontrado):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "code": "CANVAS_NOT_FOUND",
                "message": str(exc),
                "details": getattr(exc, "details", []),
            },
        )

    @app.exception_handler(ElementoNoEncontrado)
    async def element_not_found_handler(request: Request, exc: ElementoNoEncontrado):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "code": "ELEMENT_NOT_FOUND",
                "message": str(exc),
                "details": getattr(exc, "details", []),
            },
        )

    @app.exception_handler(UmlValidationError)
    async def uml_validation_error_handler(request: Request, exc: UmlValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": "UML_INVALID_MODEL",
                "message": str(exc),
                "details": getattr(exc, "details", []),
            },
        )

    @app.exception_handler(ConcurrentEditConflict)
    async def concurrent_conflict_handler(request: Request, exc: ConcurrentEditConflict):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": "CONCURRENT_EDIT_CONFLICT",
                "message": str(exc),
                "details": getattr(exc, "details", []),
            },
        )

    @app.exception_handler(UnsupportedGenerationFeature)
    async def unsupported_feature_handler(request: Request, exc: UnsupportedGenerationFeature):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "UNSUPPORTED_GENERATION_FEATURE",
                "message": str(exc),
                "details": getattr(exc, "details", []),
            },
        )

    @app.exception_handler(UmlDomainError)
    async def uml_domain_error_handler(request: Request, exc: UmlDomainError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "UML_DOMAIN_ERROR",
                "message": str(exc),
                "details": getattr(exc, "details", []),
            },
        )
