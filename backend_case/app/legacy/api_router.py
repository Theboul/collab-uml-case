import base64
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend_case.app.legacy.database import get_legacy_db
from backend_case.app.legacy.flutter_generator import FlutterCRUDGenerator
from backend_case.app.legacy.models import BackupUMLRecord
from backend_case.app.legacy.services_gemini import call_gemini, call_gemini_from_image
from backend_case.app.legacy.zip_utils import compress_folder_to_zip

legacy_api_router = APIRouter(prefix="/api", tags=["Legacy Compatibility API"])


def _validar_estructura_uml_json(parsed: Any) -> str | None:
    """
    Sanity check estructural sobre el JSON crudo que devuelve Gemini (CU6/CU7),
    antes de reenviarlo al cliente. Deliberadamente NO es UMLValidator: este
    endpoint legacy también acepta diffs parciales de edición incremental
    ("elimina la clase Usuario" -> {"classes": [{"name": "Usuario", "eliminar": true}]},
    sin id ni atributos) y una respuesta de dos JSONs para edición
    ({"original": {...}, "editado": {...}}) — exigir un modelo UML completo
    rechazaría esos casos legítimos como si fueran errores.

    Solo rechaza basura estructural real: que no sea un objeto, que
    'classes'/'relationships' no sean listas, o que sus elementos no sean
    objetos con el campo mínimo indispensable. Si esas claves no están en la
    raíz (ej. el modo de edición con "original"/"editado"), no valida nada
    y deja pasar — está fuera del alcance de este chequeo.
    """
    if not isinstance(parsed, dict):
        return "la respuesta no es un objeto JSON"

    for key in ("classes", "relationships"):
        if key not in parsed:
            continue
        items = parsed[key]
        if not isinstance(items, list):
            return f"'{key}' debe ser una lista"
        for item in items:
            if not isinstance(item, dict):
                return f"cada elemento de '{key}' debe ser un objeto"
            if key == "classes" and not item.get("name"):
                return "cada clase debe tener 'name'"
            if key == "relationships" and not item.get("sourceId"):
                return "cada relación debe tener 'sourceId'"

    return None


# 1. Chatbot UML Generation
@legacy_api_router.post("/chatbot/")
@legacy_api_router.post("/chatbot")
async def generate_uml_chatbot(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "El campo 'prompt' es requerido"},
        )

    output = call_gemini(prompt)

    # Clean markdown if enclosed in ```json ... ```
    if isinstance(output, str):
        output = re.sub(r"^```json\s*|\s*```$", "", output.strip(), flags=re.MULTILINE)

    try:
        parsed_json = json.loads(output)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Gemini devolvió un formato inválido",
                "raw": output,
                "exception": str(e),
            },
        )

    error_estructura = _validar_estructura_uml_json(parsed_json)
    if error_estructura:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": f"Gemini devolvió una estructura UML inválida: {error_estructura}",
                "raw": parsed_json,
            },
        )

    return JSONResponse(status_code=status.HTTP_200_OK, content=parsed_json)


def _get_room_id_candidates(room_id: str) -> list[str]:
    import uuid
    raw = str(room_id).strip()
    candidates = [raw]
    try:
        u = uuid.UUID(raw)
        if str(u) not in candidates:
            candidates.append(str(u))
        if u.hex not in candidates:
            candidates.append(u.hex)
    except Exception:
        pass
    return candidates


# 2. Set Backup UML
@legacy_api_router.post("/set_backup_uml/{room_id}/")
@legacy_api_router.post("/set_backup_uml/{room_id}")
async def set_backup_uml(
    room_id: str,
    request: Request,
    db: AsyncSession = Depends(get_legacy_db),
):
    if not room_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Se requiere el campo 'room_id'"},
        )

    try:
        data = await request.json()
    except Exception:
        data = {}

    try:
        candidates = _get_room_id_candidates(room_id)
        stmt = select(BackupUMLRecord).where(BackupUMLRecord.room_id.in_(candidates))
        result = await db.execute(stmt)
        record = result.scalars().first()

        created = False
        if record:
            record.data = data
        else:
            record = BackupUMLRecord(room_id=str(room_id), data=data)
            db.add(record)
            created = True

        await db.commit()
        await db.refresh(record)

        resp_data = record.data
        if isinstance(resp_data, str):
            try:
                resp_data = json.loads(resp_data)
            except Exception:
                pass

        return JSONResponse(
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            content={
                "message": "UML creado con éxito" if created else "UML actualizado con éxito",
                "room_id": str(record.room_id),
                "data": resp_data,
            },
        )
    except Exception as e:
        await db.rollback()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e)},
        )


# 3. Get Backup UML
@legacy_api_router.get("/get_backup_uml/{room_id}/")
@legacy_api_router.get("/get_backup_uml/{room_id}")
async def get_backup_uml(
    room_id: str,
    db: AsyncSession = Depends(get_legacy_db),
):
    if not room_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Se requiere el campo 'room_id'"},
        )

    candidates = _get_room_id_candidates(room_id)
    stmt = select(BackupUMLRecord).where(BackupUMLRecord.room_id.in_(candidates))
    result = await db.execute(stmt)
    record = result.scalars().first()

    if not record:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "No existe un diagrama con ese ID"},
        )

    data = record.data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass

    return JSONResponse(status_code=status.HTTP_200_OK, content=data)



# 4. Analyze UML Image
@legacy_api_router.post("/uml_from_image/")
@legacy_api_router.post("/uml_from_image")
async def analyze_uml_image(
    image: UploadFile = File(None),
):
    if not image:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Debe enviar un archivo 'image'"},
        )

    content = await image.read()
    if not content:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Debe enviar un archivo 'image'"},
        )

    image_base64 = base64.b64encode(content).decode("utf-8")
    mime_type = image.content_type or "image/png"

    result = call_gemini_from_image(image_base64, mime_type=mime_type)

    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except Exception:
        parsed = {"raw": result, "error": "No se pudo parsear correctamente"}
    else:
        error_estructura = _validar_estructura_uml_json(parsed)
        if error_estructura:
            parsed = {"raw": parsed, "error": f"Estructura UML inválida: {error_estructura}"}

    return JSONResponse(status_code=status.HTTP_200_OK, content={"uml_json": parsed})


# 5. Generar Flutter CRUD
@legacy_api_router.post("/generar_flutter/")
@legacy_api_router.post("/generar_flutter")
async def generar_flutter(request: Request):
    try:
        uml_json = await request.json()
    except Exception:
        uml_json = {}

    if not uml_json.get("classes"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "El JSON UML debe contener 'classes'."},
        )

    temp_dir: Path | None = None
    zip_path: Path | None = None
    try:
        temp_dir = Path(tempfile.mkdtemp())
        output_app_dir = temp_dir / "flutter_app"

        generator = FlutterCRUDGenerator(uml_json)
        generator.generate_project(output_dir=output_app_dir)

        zip_path = compress_folder_to_zip(output_app_dir)

        cleanup = BackgroundTasks()
        cleanup.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        cleanup.add_task(zip_path.unlink, missing_ok=True)

        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename="flutter_project.zip",
            headers={"Content-Disposition": 'attachment; filename="flutter_project.zip"'},
            background=cleanup,
        )
    except Exception as e:
        cleanup = BackgroundTasks()
        if temp_dir is not None:
            cleanup.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        if zip_path is not None:
            cleanup.add_task(zip_path.unlink, missing_ok=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)},
            background=cleanup,
        )
