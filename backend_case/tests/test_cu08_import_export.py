"""
CU8: Importar y exportar modelos UML vía XMI 1.1/UML 1.3 (Enterprise Architect).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app

_FIXTURE_PATH = "docs/spec/ejemplo de diagrama de clases ea.xml"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_user(client: TestClient, email_prefix: str) -> str:
    """Registra un usuario nuevo con email único y devuelve su accessToken."""
    email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@schemacraft.dev"
    res = client.post(
        "/api/v2/auth/register",
        json={"email": email, "password": "Password123!", "fullName": "Test User"},
    )
    assert res.status_code == 201, res.text
    return res.json()["accessToken"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _import_real_ea_file(client: TestClient) -> dict:
    with open(_FIXTURE_PATH, "rb") as f:
        content = f.read()
    res = client.post(
        "/api/v2/canvases/import",
        files={"file": ("ejemplo.xml", content, "application/xml")},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_import_real_ea_file_produces_expected_model(client: TestClient):
    """
    Importa el archivo XMI 1.1/UML 1.3 real exportado por Enterprise Architect
    (docs/spec/ejemplo de diagrama de clases ea.xml) y confirma que el modelo
    normalizado tiene exactamente las 3 clases, 2 asociaciones, atributos/
    operaciones/parámetros y posición x/y reales del archivo.
    """
    data = _import_real_ea_file(client)
    model = data["canvas"]["model"]

    assert data["validation"]["valid"] is True
    assert data["validation"]["errors"] == []

    class_names = sorted(c["name"] for c in model["classes"])
    assert class_names == ["Class A", "Class B", "Class C"]
    assert len(model["associations"]) == 2

    class_a = next(c for c in model["classes"] if c["name"] == "Class A")
    assert sorted((a["name"], a["type"]) for a in class_a["attributes"]) == [
        ("Attribute A", "int"),
        ("Attribute B", "int"),
    ]
    op_a = next(o for o in class_a["operations"] if o["name"] == "Operation A")
    assert op_a["returnType"] == "void"
    assert [p["name"] for p in op_a["parameters"]] == ["Parameter A"]

    id_to_name = {c["id"]: c["name"] for c in model["classes"]}
    assoc_pairs = sorted(
        (id_to_name[a["memberEnds"][0]["classId"]], id_to_name[a["memberEnds"][1]["classId"]])
        for a in model["associations"]
    )
    assert assoc_pairs == [("Class A", "Class B"), ("Class A", "Class C")]

    class_a_id = class_a["id"]
    nodes = data["canvas"]["visualLayout"]["nodes"]
    assert class_a_id in nodes
    assert nodes[class_a_id]["x"] == 100.0
    assert nodes[class_a_id]["y"] == 100.0


def test_import_malformed_xml_returns_422(client: TestClient):
    """Un archivo que ni siquiera es XML bien formado debe rechazarse con 422 XMI_PARSE_ERROR."""
    res = client.post(
        "/api/v2/canvases/import",
        files={"file": ("roto.xml", b"<XMI><no-cierra>", "application/xml")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "XMI_PARSE_ERROR"


def test_export_generates_well_formed_xmi_with_expected_elements(client: TestClient):
    """Exportar un lienzo creado por comandos normales debe producir un XMI bien formado."""
    import xml.etree.ElementTree as ET

    create_res = client.post("/api/v2/canvases", json={"name": "Lienzo Export"})
    canvas_id = create_res.json()["id"]

    c1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"name": "Cliente", "x": 10, "y": 20},
        },
    )
    cliente_id = c1.json()["canvas"]["model"]["classes"][0]["id"]

    c2 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 2,
            "type": "CREATE_CLASS",
            "payload": {"name": "Pedido", "x": 300, "y": 20},
        },
    )
    pedido_id = c2.json()["canvas"]["model"]["classes"][1]["id"]

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": cliente_id,
                "targetClassId": pedido_id,
                "type": "ASSOCIATION",
                "sourceMultiplicity": "1",
                "targetMultiplicity": "0..*",
            },
        },
    )

    export_res = client.get(f"/api/v2/canvases/{canvas_id}/export/xmi")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(export_res.content)
    ns = "{omg.org/UML1.3}"
    class_names = sorted(el.get("name") for el in root.iter(f"{ns}Class"))
    assert class_names == ["Cliente", "Pedido"]
    assert len(list(root.iter(f"{ns}Association"))) == 1


def test_export_then_reimport_roundtrip_is_semantically_equivalent(client: TestClient):
    """
    Round-trip completo: importar el archivo real de EA, exportarlo, reimportar el
    resultado, y confirmar que las clases/atributos/operaciones/asociaciones
    resultantes son semánticamente equivalentes (no necesariamente mismos IDs).
    """
    imported = _import_real_ea_file(client)
    canvas_id = imported["canvas"]["id"]

    export_res = client.get(f"/api/v2/canvases/{canvas_id}/export/xmi")
    assert export_res.status_code == 200

    reimport_res = client.post(
        "/api/v2/canvases/import",
        files={"file": ("roundtrip.xml", export_res.content, "application/xml")},
    )
    assert reimport_res.status_code == 201

    def summarize(model: dict) -> list:
        return sorted(
            (
                c["name"],
                c["isAbstract"],
                tuple(sorted((a["name"], a["type"]) for a in c["attributes"])),
                tuple(
                    sorted(
                        (o["name"], o["returnType"], tuple(p["name"] for p in o["parameters"]))
                        for o in c["operations"]
                    )
                ),
            )
            for c in model["classes"]
        )

    original_model = imported["canvas"]["model"]
    roundtrip_model = reimport_res.json()["canvas"]["model"]
    assert summarize(original_model) == summarize(roundtrip_model)
    assert len(original_model["associations"]) == len(roundtrip_model["associations"])


def test_export_forbidden_for_user_without_access(client: TestClient):
    """Hallazgo #1 de la auditoría, extendido a CU8: un rol INVITADO no puede exportar."""
    owner_token = _register_user(client, "owner-export-403")
    outsider_token = _register_user(client, "outsider-export-403")

    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Privado Export"},
        headers=_auth_headers(owner_token),
    )
    canvas_id = create_res.json()["id"]

    outsider_res = client.get(
        f"/api/v2/canvases/{canvas_id}/export/xmi", headers=_auth_headers(outsider_token)
    )
    assert outsider_res.status_code == 403
    assert outsider_res.json()["code"] == "CANVAS_ACCESS_FORBIDDEN"

    owner_res = client.get(
        f"/api/v2/canvases/{canvas_id}/export/xmi", headers=_auth_headers(owner_token)
    )
    assert owner_res.status_code == 200
