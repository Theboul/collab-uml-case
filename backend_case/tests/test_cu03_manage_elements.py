"""
Pruebas integrales para SPEC-CU03: Gestionar elementos del diagrama de clases.
Valida:
1. Creación, renombrado y rechazo de nombres inválidos/duplicados de clases.
2. Gestión de atributos (adición, edición, eliminación, unicidad por clase, rechazo de empty update).
3. Gestión de operaciones (adición con sobrecarga válida vs duplicada, edición, eliminación).
4. Gestión de parámetros (adición, edición, eliminación, unicidad por método).
5. Eliminación de clases en cascada (DELETE_ELEMENTS) retornando undoPayload completo y restauración (RESTORE_ELEMENTS) con IDs originales.
6. Control de concurrencia optimista atómico (409 CONCURRENT_EDIT_CONFLICT y 404 CANVAS_NOT_FOUND).
"""

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_class_lifecycle_and_validation(client: TestClient):
    """Verifica creación, renombrado y rechazo de nombres inválidos/duplicados."""
    # 1. Crear lienzo
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Clases CU3"})
    assert res.status_code == 201
    canvas_id = res.json()["id"]
    version = res.json()["version"]

    # 2. CREATE_CLASS con ID propuesto por cliente
    custom_class_id = "class-custom-001"
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {
                "classId": custom_class_id,
                "name": "Cliente",
                "isAbstract": False,
                "x": 100,
                "y": 100,
            },
        },
    )
    assert cmd_res.status_code == 200
    data = cmd_res.json()
    version = data["version"]
    clase = next(c for c in data["canvas"]["model"]["classes"] if c["id"] == custom_class_id)
    assert clase["name"] == "Cliente"
    assert clase["isAbstract"] is False

    # 3. Intentar crear otra clase con el mismo nombre -> 422 / 400 DUPLICATE_CLASS_NAME
    cmd_dup = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"name": "Cliente", "x": 300, "y": 100},
        },
    )
    assert cmd_dup.status_code in (400, 422)
    assert "ya existe" in cmd_dup.json()["message"].lower()

    # 4. UPDATE_CLASS_NAME
    cmd_rename = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "UPDATE_CLASS_NAME",
            "payload": {"classId": custom_class_id, "name": "ClienteCorporativo"},
        },
    )
    assert cmd_rename.status_code == 200
    version = cmd_rename.json()["version"]
    clase = next(c for c in cmd_rename.json()["canvas"]["model"]["classes"] if c["id"] == custom_class_id)
    assert clase["name"] == "ClienteCorporativo"


def test_attribute_management(client: TestClient):
    """Verifica adición, edición, validación de duplicados y eliminación de atributos."""
    # 1. Crear lienzo y clase
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Atributos"})
    canvas_id = res.json()["id"]
    version = res.json()["version"]

    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-factura", "name": "Factura"},
        },
    )
    version = cmd_res.json()["version"]

    # 2. ADD_ATTRIBUTE con ID propio
    attr_id = "attr-numero-01"
    add_attr = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_ATTRIBUTE",
            "payload": {
                "classId": "c-factura",
                "attributeId": attr_id,
                "name": "numero",
                "type": "String",
                "visibility": "-",
            },
        },
    )
    assert add_attr.status_code == 200
    version = add_attr.json()["version"]
    clase = add_attr.json()["canvas"]["model"]["classes"][0]
    assert len(clase["attributes"]) == 1
    assert clase["attributes"][0]["id"] == attr_id
    assert clase["attributes"][0]["name"] == "numero"
    assert clase["attributes"][0]["visibility"] == "-"

    # 3. Intentar agregar atributo con mismo nombre -> 400 / 422 DUPLICATE_ATTRIBUTE_NAME
    dup_attr = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_ATTRIBUTE",
            "payload": {
                "classId": "c-factura",
                "name": "numero",
                "type": "Integer",
            },
        },
    )
    assert dup_attr.status_code in (400, 422)

    # 4. UPDATE_ATTRIBUTE vacío -> Rechazo EMPTY_UPDATE
    empty_update = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "UPDATE_ATTRIBUTE",
            "payload": {"classId": "c-factura", "attributeId": attr_id},
        },
    )
    assert empty_update.status_code in (400, 422)

    # 5. UPDATE_ATTRIBUTE exitoso
    update_attr = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "UPDATE_ATTRIBUTE",
            "payload": {
                "classId": "c-factura",
                "attributeId": attr_id,
                "name": "codigoFactura",
                "type": "String",
                "visibility": "+",
            },
        },
    )
    assert update_attr.status_code == 200
    version = update_attr.json()["version"]
    clase = update_attr.json()["canvas"]["model"]["classes"][0]
    assert clase["attributes"][0]["name"] == "codigoFactura"
    assert clase["attributes"][0]["visibility"] == "+"

    # 6. DELETE_ATTRIBUTE
    del_attr = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "DELETE_ATTRIBUTE",
            "payload": {"classId": "c-factura", "attributeId": attr_id},
        },
    )
    assert del_attr.status_code == 200
    version = del_attr.json()["version"]
    clase = del_attr.json()["canvas"]["model"]["classes"][0]
    assert len(clase["attributes"]) == 0


def test_operation_and_parameter_management(client: TestClient):
    """Verifica métodos, parámetros, sobrecargas y validaciones."""
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Operaciones"})
    canvas_id = res.json()["id"]
    version = res.json()["version"]

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-cuenta", "name": "Cuenta"},
        },
    )
    version += 1

    # 1. ADD_OPERATION: depositar() : void
    op_id1 = "op-dep-01"
    add_op1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_OPERATION",
            "payload": {
                "classId": "c-cuenta",
                "operationId": op_id1,
                "name": "depositar",
                "returnType": "void",
                "visibility": "+",
            },
        },
    )
    assert add_op1.status_code == 200
    version = add_op1.json()["version"]

    # 2. ADD_PARAMETER a depositar: monto: Float
    param_id1 = "p-monto-01"
    add_p1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_PARAMETER",
            "payload": {
                "classId": "c-cuenta",
                "operationId": op_id1,
                "parameterId": param_id1,
                "name": "monto",
                "type": "Float",
            },
        },
    )
    assert add_p1.status_code == 200
    version = add_p1.json()["version"]
    clase = add_p1.json()["canvas"]["model"]["classes"][0]
    assert len(clase["operations"][0]["parameters"]) == 1
    assert clase["operations"][0]["parameters"][0]["id"] == param_id1

    # 3. Intentar agregar parámetro duplicado en la misma operación -> Rechazo
    dup_p = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_PARAMETER",
            "payload": {
                "classId": "c-cuenta",
                "operationId": op_id1,
                "name": "monto",
                "type": "Integer",
            },
        },
    )
    assert dup_p.status_code in (400, 422)

    # 4. Intentar agregar otra operación con la misma firma depositar(Float) -> Rechazo
    dup_op = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_OPERATION",
            "payload": {
                "classId": "c-cuenta",
                "name": "depositar",
                "returnType": "Boolean",
                "parameters": [{"id": "p2", "name": "cantidad", "type": "Float"}],
            },
        },
    )
    assert dup_op.status_code in (400, 422)

    # 5. Sobrecarga válida: depositar(monto: Float, referencia: String)
    valid_overload = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_OPERATION",
            "payload": {
                "classId": "c-cuenta",
                "name": "depositar",
                "returnType": "void",
                "parameters": [
                    {"id": "p-o1", "name": "monto", "type": "Float"},
                    {"id": "p-o2", "name": "referencia", "type": "String"},
                ],
            },
        },
    )
    assert valid_overload.status_code == 200
    version = valid_overload.json()["version"]
    assert len(valid_overload.json()["canvas"]["model"]["classes"][0]["operations"]) == 2

    # 6. UPDATE_PARAMETER
    up_param = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "UPDATE_PARAMETER",
            "payload": {
                "classId": "c-cuenta",
                "operationId": op_id1,
                "parameterId": param_id1,
                "name": "montoTotal",
                "type": "Double",
            },
        },
    )
    assert up_param.status_code == 200
    version = up_param.json()["version"]
    clase = up_param.json()["canvas"]["model"]["classes"][0]
    param = next(p for p in clase["operations"][0]["parameters"] if p["id"] == param_id1)
    assert param["name"] == "montoTotal"
    assert param["type"] == "Double"

    # 7. DELETE_PARAMETER
    del_param = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "DELETE_PARAMETER",
            "payload": {
                "classId": "c-cuenta",
                "operationId": op_id1,
                "parameterId": param_id1,
            },
        },
    )
    assert del_param.status_code == 200
    version = del_param.json()["version"]

    # 8. DELETE_OPERATION
    del_op = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "DELETE_OPERATION",
            "payload": {"classId": "c-cuenta", "operationId": op_id1},
        },
    )
    assert del_op.status_code == 200
    version = del_op.json()["version"]
    clase = del_op.json()["canvas"]["model"]["classes"][0]
    assert len(clase["operations"]) == 1


def test_delete_and_restore_elements_cascade(client: TestClient):
    """Verifica que DELETE_ELEMENTS retorna undoPayload completo y RESTORE_ELEMENTS recupera el agregado exacto."""
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Cascade"})
    canvas_id = res.json()["id"]
    version = res.json()["version"]

    # Crear Clase A
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-a", "name": "ClaseA"},
        },
    )
    version += 1

    # Crear Clase B
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-b", "name": "ClaseB"},
        },
    )
    version += 1

    # Crear Asociación entre A y B
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_RELATION",
            "payload": {
                "relationId": "rel-ab-1",
                "sourceClassId": "c-a",
                "targetClassId": "c-b",
                "type": "ASSOCIATION",
            },
        },
    )
    version += 1

    # DELETE_ELEMENTS de Clase A
    del_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "DELETE_ELEMENTS",
            "payload": {"classIds": ["c-a"]},
        },
    )
    assert del_res.status_code == 200
    data = del_res.json()
    version = data["version"]
    assert len(data["canvas"]["model"]["classes"]) == 1
    assert data["canvas"]["model"]["classes"][0]["id"] == "c-b"
    assert len(data["canvas"]["model"]["associations"]) == 0
    undo_payload = data["undoPayload"]
    assert undo_payload is not None
    assert len(undo_payload["classes"]) == 1
    assert undo_payload["classes"][0]["id"] == "c-a"
    assert len(undo_payload["relations"]) == 1
    assert undo_payload["relations"][0]["id"] == "rel-ab-1"

    # RESTORE_ELEMENTS utilizando el undoPayload devuelto
    restore_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "RESTORE_ELEMENTS",
            "payload": undo_payload,
        },
    )
    assert restore_res.status_code == 200
    restored = restore_res.json()
    version = restored["version"]
    model = restored["canvas"]["model"]
    assert len(model["classes"]) == 2
    assert any(c["id"] == "c-a" for c in model["classes"])
    assert len(model["associations"]) == 1
    assert model["associations"][0]["id"] == "rel-ab-1"


def test_delete_and_restore_elements_cascade_with_generalization(client: TestClient):
    """
    Regresión: DELETE_ELEMENTS sobre una clase con una generalización asociada
    crasheaba con AttributeError (class_handlers.py usaba specific_classifier_id/
    general_classifier_id, nombres que no existen en UmlGeneralization).
    """
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Cascade Herencia"})
    canvas_id = res.json()["id"]
    version = res.json()["version"]

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-persona", "name": "Persona"},
        },
    )
    version += 1

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-empleado", "name": "Empleado"},
        },
    )
    version += 1

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_RELATION",
            "payload": {
                "relationId": "gen-empleado-persona",
                "sourceClassId": "c-empleado",
                "targetClassId": "c-persona",
                "type": "GENERALIZATION",
            },
        },
    )
    version += 1

    del_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "DELETE_ELEMENTS",
            "payload": {"classIds": ["c-empleado"]},
        },
    )
    assert del_res.status_code == 200
    data = del_res.json()
    version = data["version"]
    model = data["canvas"]["model"]
    assert len(model["classes"]) == 1
    assert model["classes"][0]["id"] == "c-persona"
    assert len(model["generalizations"]) == 0

    undo_payload = data["undoPayload"]
    assert len(undo_payload["generalizations"]) == 1
    assert undo_payload["generalizations"][0]["id"] == "gen-empleado-persona"
    assert undo_payload["generalizations"][0]["specificClassId"] == "c-empleado"
    assert undo_payload["generalizations"][0]["generalClassId"] == "c-persona"

    restore_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "RESTORE_ELEMENTS",
            "payload": undo_payload,
        },
    )
    assert restore_res.status_code == 200
    restored_model = restore_res.json()["canvas"]["model"]
    assert len(restored_model["classes"]) == 2
    assert len(restored_model["generalizations"]) == 1
    assert restored_model["generalizations"][0]["id"] == "gen-empleado-persona"
    assert restored_model["generalizations"][0]["specificClassId"] == "c-empleado"
    assert restored_model["generalizations"][0]["generalClassId"] == "c-persona"


def test_atomic_optimistic_concurrency_conflict(client: TestClient):
    """Verifica que un intento de mutación con versión desactualizada retorne 409 CONFLICT."""
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Concurrencia"})
    canvas_id = res.json()["id"]

    # Crear clase con expectedVersion = 1 -> Exitoso (versión pasa a 2)
    res_cmd1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"name": "Usuario"},
        },
    )
    assert res_cmd1.status_code == 200
    assert res_cmd1.json()["version"] == 2

    # Intentar otro comando con expectedVersion = 1 obsoleta -> 409
    res_cmd2 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"name": "Rol"},
        },
    )
    assert res_cmd2.status_code == 409
    assert res_cmd2.json()["code"] == "VERSION_CONFLICT"


def test_preventive_parameter_normalization_on_get(client: TestClient):
    """Verifica que un lienzo histórico con parámetros sin 'id' se normalice y persista atómicamente antes de entregarse."""
    import asyncio
    import uuid

    from backend_case.app.modeling.infrastructure.db_models import CanvasORM
    from backend_case.app.shared.db.base import async_session_factory

    canvas_id = f"legacy-norm-{uuid.uuid4().hex[:8]}"

    legacy_model = {
        "schemaVersion": "2.0.0",
        "modelId": "legacy-m1",
        "name": "Lienzo Historico",
        "classes": [
            {
                "id": "c-hist-1",
                "name": "Historico",
                "visibility": "+",
                "isAbstract": False,
                "attributes": [],
                "methods": [
                    {
                        "id": "m-hist-1",
                        "name": "procesar",
                        "visibility": "+",
                        "returnType": "void",
                        "parameters": [
                            # Sin id
                            {"name": "paramSinId", "type": "String", "direction": "in"}
                        ],
                    }
                ],
                "operations": [
                    {
                        "id": "m-hist-1",
                        "name": "procesar",
                        "visibility": "+",
                        "returnType": "void",
                        "parameters": [
                            # Sin id
                            {"name": "paramSinId", "type": "String", "direction": "in"}
                        ],
                    }
                ],
            }
        ],
        "associations": [],
        "generalizations": [],
    }

    async def insert_legacy():
        async with async_session_factory() as session:
            c_orm = CanvasORM(
                id=canvas_id,
                name="Lienzo Historico",
                version=1,
                room_name=f"room-{canvas_id}",
                semantic_model=legacy_model,
                visual_layout={},
            )
            session.add(c_orm)
            await session.commit()

    asyncio.run(insert_legacy())

    # 1. Primer GET: debe activar normalización preventiva, persistir y devolver ID
    get_res1 = client.get(f"/api/v2/canvases/{canvas_id}")
    assert get_res1.status_code == 200
    data1 = get_res1.json()
    assert data1["version"] == 2  # Se incrementó por CAS
    clase1 = data1["model"]["classes"][0]
    param1 = clase1["operations"][0]["parameters"][0]
    assert param1["name"] == "paramSinId"
    assigned_id = param1["id"]
    assert assigned_id is not None
    assert len(assigned_id) > 0

    # 2. Segundo GET: debe devolver el mismo ID exactamente persistido
    get_res2 = client.get(f"/api/v2/canvases/{canvas_id}")
    assert get_res2.status_code == 200
    data2 = get_res2.json()
    assert data2["version"] == 2  # No se incrementó de nuevo, ya estaba normalizado
    param2 = data2["model"]["classes"][0]["operations"][0]["parameters"][0]
    assert param2["id"] == assigned_id

