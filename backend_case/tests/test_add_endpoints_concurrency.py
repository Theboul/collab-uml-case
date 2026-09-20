"""
`POST /classes` y `POST /associations` no reciben una versión del cliente: su protección contra
lost-update es la versión leída dentro de la propia petición (guardado atómico). Si otro escritor
confirma un cambio entre esa lectura y el guardado, la petición debe fallar con 409 y NO pisar el
cambio ajeno.
"""

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository
from backend_case.app.shared.db.base import async_session_factory


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def escritor_concurrente(monkeypatch):
    """
    Tras la lectura que hace el endpoint bajo prueba, otro escritor confirma un cambio en su propia
    sesión: agrega la clase "Competidora". Solo actúa una vez, cuando `estado["activo"]` está
    encendido, para no reentrar con las lecturas posteriores.
    """
    obtener_real = CanvasRepository.obtener
    estado = {"activo": False, "disparado": False}

    async def obtener_con_competidor(self, canvas_id):
        res = await obtener_real(self, canvas_id)
        if estado["activo"] and not estado["disparado"]:
            estado["disparado"] = True
            async with async_session_factory() as otra_sesion:
                repo = CanvasRepository(otra_sesion)
                actual = await obtener_real(repo, canvas_id)
                actual.lienzo.modelo.agregar_clase("Competidora")
                await repo.guardar_atomico(canvas_id, actual.version, actual.lienzo)
                await otra_sesion.commit()
        return res

    monkeypatch.setattr(CanvasRepository, "obtener", obtener_con_competidor)
    return estado


def _modelo(client: TestClient, canvas_id: str) -> dict:
    return client.get(f"/api/v2/canvases/{canvas_id}").json()["model"]


def test_add_class_no_pisa_un_cambio_concurrente(client, escritor_concurrente):
    canvas_id = client.post("/api/v2/canvases", json={"name": "Lienzo Concurrencia"}).json()["id"]
    escritor_concurrente["activo"] = True

    res = client.post(f"/api/v2/canvases/{canvas_id}/classes", json={"name": "Cliente"})

    assert res.status_code == 409
    assert res.json()["code"] == "VERSION_CONFLICT"
    # El cambio del otro escritor sobrevive; la petición rechazada no dejó rastro.
    assert [c["name"] for c in _modelo(client, canvas_id)["classes"]] == ["Competidora"]


def test_add_association_no_pisa_un_cambio_concurrente(client, escritor_concurrente):
    canvas_id = client.post("/api/v2/canvases", json={"name": "Lienzo Concurrencia"}).json()["id"]
    client.post(f"/api/v2/canvases/{canvas_id}/classes", json={"name": "Pedido"})
    modelo = client.post(f"/api/v2/canvases/{canvas_id}/classes", json={"name": "Factura"}).json()[
        "model"
    ]
    ids = {c["name"]: c["id"] for c in modelo["classes"]}
    escritor_concurrente["activo"] = True

    res = client.post(
        f"/api/v2/canvases/{canvas_id}/associations",
        json={"sourceClassId": ids["Pedido"], "targetClassId": ids["Factura"], "name": "genera"},
    )

    assert res.status_code == 409
    assert res.json()["code"] == "VERSION_CONFLICT"
    modelo_final = _modelo(client, canvas_id)
    assert modelo_final["associations"] == []
    nombres = sorted(c["name"] for c in modelo_final["classes"])
    assert nombres == ["Competidora", "Factura", "Pedido"]
