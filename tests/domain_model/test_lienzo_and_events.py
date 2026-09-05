import pytest

from core.uml_domain.events import ElementoAgregado, LienzoCreado, RelacionAgregada
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import Lienzo, UmlDomainModel


def test_crear_nuevo_lienzo_cu1():
    lienzo, evento = Lienzo.crear_nuevo()

    assert lienzo.id == lienzo.modelo.model_id  # Mismo identificador unificado
    assert lienzo.modelo.classes == []
    assert lienzo.modelo.schema_version == "2.0.0"
    assert isinstance(evento, LienzoCreado)
    assert evento.lienzo_id == lienzo.id


def test_agregar_clase_devuelve_evento_cu3():
    modelo = UmlDomainModel()

    clase, evento = modelo.agregar_clase("Cliente")

    assert clase in modelo.classes
    assert isinstance(evento, ElementoAgregado)
    assert evento.elemento_id == clase.id
    assert evento.tipo == "UmlClass"


def test_no_permite_clasificadores_duplicados():
    modelo = UmlDomainModel()
    modelo.agregar_clase("Cliente")

    with pytest.raises(UmlValidationError):
        modelo.agregar_clase("Cliente")


def test_agregar_asociacion_devuelve_evento_cu4():
    modelo = UmlDomainModel()
    origen, _ = modelo.agregar_clase("Pedido")
    destino, _ = modelo.agregar_clase("Cliente")

    asociacion, evento = modelo.agregar_asociacion(origen.id, destino.id, nombre="realiza")

    assert asociacion in modelo.associations
    assert isinstance(evento, RelacionAgregada)
    assert evento.relacion_id == asociacion.id
    assert evento.tipo == "UmlAssociation"


def test_agregar_asociacion_rechaza_elemento_inexistente():
    modelo = UmlDomainModel()
    origen, _ = modelo.agregar_clase("Pedido")

    with pytest.raises(ElementoNoEncontrado):
        modelo.agregar_asociacion(origen.id, "id-inexistente")


def test_find_classifier_by_id_sigue_funcionando():
    modelo = UmlDomainModel()
    clase, _ = modelo.agregar_clase("Cliente")

    assert modelo.find_classifier_by_id(clase.id) is clase
    assert modelo.find_classifier_by_id("no-existe") is None
