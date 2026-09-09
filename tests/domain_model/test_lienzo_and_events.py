import pytest

from core.uml_domain.events import (
    ElementoAgregado,
    LienzoCreado,
    RelacionAgregada,
    RelacionEliminada,
    RelacionModificada,
)
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import (
    AggregationKind,
    Lienzo,
    MultiplicityRange,
    UmlDomainModel,
    UmlGeneralization,
)


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


def test_editar_asociacion_muta_campos_provistos_y_devuelve_evento_cu4():
    modelo = UmlDomainModel()
    origen, _ = modelo.agregar_clase("Pedido")
    destino, _ = modelo.agregar_clase("Cliente")
    asociacion, _ = modelo.agregar_asociacion(origen.id, destino.id, nombre="realiza")

    editada, evento = modelo.editar_asociacion(
        asociacion.id,
        nombre="contiene",
        rol_origen="pedidoRol",
        rol_destino="clienteRol",
        multiplicidad_origen=MultiplicityRange(0, None),
        multiplicidad_destino=MultiplicityRange(1, 1),
        agregacion_origen=AggregationKind.COMPOSITE,
    )

    assert editada is asociacion
    assert asociacion.name == "contiene"
    assert asociacion.member_ends[0].role_name == "pedidoRol"
    assert asociacion.member_ends[1].role_name == "clienteRol"
    assert asociacion.member_ends[0].multiplicity == MultiplicityRange(0, None)
    assert asociacion.member_ends[1].multiplicity == MultiplicityRange(1, 1)
    assert asociacion.member_ends[0].aggregation_kind == AggregationKind.COMPOSITE
    assert isinstance(evento, RelacionModificada)
    assert evento.relacion_id == asociacion.id
    assert evento.tipo == "UmlAssociation"


def test_editar_asociacion_rechaza_id_inexistente():
    modelo = UmlDomainModel()

    with pytest.raises(ElementoNoEncontrado):
        modelo.editar_asociacion("id-inexistente", nombre="nuevo-nombre")


def test_eliminar_asociacion_la_remueve_y_devuelve_evento_cu4():
    modelo = UmlDomainModel()
    origen, _ = modelo.agregar_clase("Pedido")
    destino, _ = modelo.agregar_clase("Cliente")
    asociacion, _ = modelo.agregar_asociacion(origen.id, destino.id)

    evento = modelo.eliminar_asociacion(asociacion.id)

    assert asociacion not in modelo.associations
    assert isinstance(evento, RelacionEliminada)
    assert evento.relacion_id == asociacion.id
    assert evento.tipo == "UmlAssociation"


def test_eliminar_asociacion_rechaza_id_inexistente():
    modelo = UmlDomainModel()

    with pytest.raises(ElementoNoEncontrado):
        modelo.eliminar_asociacion("id-inexistente")


def test_agregar_generalizacion_devuelve_evento_cu4():
    modelo = UmlDomainModel()
    subclase, _ = modelo.agregar_clase("ClienteVip")
    superclase, _ = modelo.agregar_clase("Cliente")

    generalizacion, evento = modelo.agregar_generalizacion(subclase.id, superclase.id)

    assert generalizacion in modelo.generalizations
    assert isinstance(generalizacion, UmlGeneralization)
    assert generalizacion.specific_class_id == subclase.id
    assert generalizacion.general_class_id == superclase.id
    assert isinstance(evento, RelacionAgregada)
    assert evento.relacion_id == generalizacion.id
    assert evento.tipo == "UmlGeneralization"


def test_agregar_generalizacion_rechaza_elemento_inexistente():
    modelo = UmlDomainModel()
    subclase, _ = modelo.agregar_clase("ClienteVip")

    with pytest.raises(ElementoNoEncontrado):
        modelo.agregar_generalizacion(subclase.id, "id-inexistente")
