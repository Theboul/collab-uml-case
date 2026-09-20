"""
Publicación de cambios en `CanvasService`: se confirma la transacción y SOLO después se avisa a los
demás. Un fallo de commit no publica nada; un fallo al publicar no revierte ni falla la petición.
"""

import logging

import pytest

from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasResult
from core.uml_domain.exceptions import ConcurrentEditConflict
from core.uml_domain.model import Lienzo

pytestmark = pytest.mark.anyio

CREAR_CLASE = ("CREATE_CLASS", {"name": "Cliente", "x": 0, "y": 0, "width": 180, "height": 100})
CREAR_OTRA = ("CREATE_CLASS", {"name": "Pedido", "x": 0, "y": 0, "width": 180, "height": 100})


class FakeRepository:
    """Registra en `calls` el orden de las operaciones de persistencia."""

    def __init__(self, calls: list[str], commit_error=None, conflict=False) -> None:
        self.calls = calls
        self.commit_error = commit_error
        self.conflict = conflict
        self._lienzo, _ = Lienzo.crear_nuevo()

    async def obtener(self, canvas_id):
        return CanvasResult(self._lienzo, 1, None, "room-x")

    async def resolver_rol(self, canvas_id, owner_id, user_id):
        return "ANFITRION"

    async def guardar_atomico(self, canvas_id, expected_version, lienzo):
        self.calls.append("guardar_atomico")
        if self.conflict:
            raise ConcurrentEditConflict("conflicto de versión")
        return CanvasResult(lienzo, expected_version + 1, None, "room-x")

    async def commit(self):
        self.calls.append("commit")
        if self.commit_error:
            raise self.commit_error


class FakePublisher:
    def __init__(self, calls: list[str], error=None) -> None:
        self.calls = calls
        self.error = error
        self.published: list[tuple[str, int, str]] = []

    async def canvas_changed(self, canvas_id, result, origin_session_id=""):
        self.calls.append("publish")
        if self.error:
            raise self.error
        self.published.append((canvas_id, result.version, origin_session_id))


def _servicio(*, commit_error=None, conflict=False, publisher_error=None, con_publicador=True):
    calls: list[str] = []
    repo = FakeRepository(calls, commit_error, conflict)
    publisher = FakePublisher(calls, publisher_error) if con_publicador else None
    return CanvasService(repo, publisher), publisher, calls


async def _ejecutar_comando(servicio, **kwargs):
    cmd_type, payload = CREAR_CLASE
    return await servicio.ejecutar_comando(
        canvas_id="c1",
        operation_id="op-1",
        expected_version=1,
        cmd_type=cmd_type,
        payload=payload,
        **kwargs,
    )


async def test_publica_despues_del_commit():
    servicio, publisher, calls = _servicio()

    await _ejecutar_comando(servicio)

    assert calls == ["guardar_atomico", "commit", "publish"]
    assert publisher.published == [("c1", 2, "")]


async def test_la_sesion_de_origen_llega_al_publicador():
    servicio, publisher, _ = _servicio()

    await _ejecutar_comando(servicio, origin_session_id="sesion-1")

    assert publisher.published == [("c1", 2, "sesion-1")]


async def test_si_el_commit_falla_la_excepcion_sube_y_no_se_publica():
    servicio, publisher, calls = _servicio(commit_error=RuntimeError("disco lleno"))

    with pytest.raises(RuntimeError, match="disco lleno"):
        await _ejecutar_comando(servicio)

    assert calls == ["guardar_atomico", "commit"]
    assert publisher.published == []


async def test_si_hay_conflicto_de_version_no_se_confirma_ni_se_publica():
    servicio, publisher, calls = _servicio(conflict=True)

    with pytest.raises(ConcurrentEditConflict):
        await _ejecutar_comando(servicio)

    assert calls == ["guardar_atomico"]
    assert publisher.published == []


async def test_un_fallo_al_publicar_no_revierte_ni_falla_la_peticion(caplog):
    servicio, _, calls = _servicio(publisher_error=RuntimeError("redis caído"))

    with caplog.at_level(logging.ERROR):
        resultado, _ = await _ejecutar_comando(servicio)

    assert resultado.version == 2  # la petición responde bien
    assert calls == ["guardar_atomico", "commit", "publish"]  # el commit ya estaba hecho
    assert "No se pudo publicar el cambio del lienzo c1" in caplog.text


async def test_sin_publicador_igual_se_confirma():
    servicio, _, calls = _servicio(con_publicador=False)

    await _ejecutar_comando(servicio)

    assert calls == ["guardar_atomico", "commit"]


async def test_el_lote_del_asistente_publica_una_vez_despues_del_commit():
    servicio, publisher, calls = _servicio()

    await servicio.ejecutar_comandos_lote(
        canvas_id="c1", expected_version=1, commands=[CREAR_CLASE, CREAR_OTRA]
    )

    assert calls == ["guardar_atomico", "commit", "publish"]
    assert publisher.published == [("c1", 2, "")]


async def test_el_flujo_secuencial_del_asistente_publica_una_vez_despues_del_commit():
    servicio, publisher, calls = _servicio()

    def resolver(item, modelo):
        return "CREATE_CLASS", {"name": item, "x": 0, "y": 0, "width": 180, "height": 100}

    await servicio.ejecutar_resolviendo_secuencial(
        canvas_id="c1", expected_version=1, raw_items=["A", "B"], resolver=resolver
    )

    assert calls == ["guardar_atomico", "commit", "publish"]
    assert publisher.published == [("c1", 2, "")]
