"""
CU3: edición de elementos desde la raíz del agregado (UmlDomainModel).

`editar_clase`, `editar_atributo` y `editar_operacion` siguen el patrón de `editar_asociacion`
(solo mutan los campos provistos), pero además:
- son dueños de las invariantes de unicidad (antes vivían en los handlers),
- validan TODO antes de mutar (una violación no deja el modelo a medias),
- devuelven `ElementoModificado` con el valor anterior y el nuevo de cada campo que cambió,
  o `None` si la edición no cambió nada.
"""

import pytest

from core.uml_domain.events import CambioCampo, ElementoModificado
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import (
    UmlAttribute,
    UmlClass,
    UmlDomainModel,
    UmlInterface,
    UmlOperation,
    UmlParameter,
    VisibilityKind,
)


def _cambios(evento: ElementoModificado | None) -> dict[str, tuple[object, object]]:
    assert evento is not None
    return {c.campo: (c.anterior, c.nuevo) for c in evento.cambios}


@pytest.fixture
def modelo() -> UmlDomainModel:
    return UmlDomainModel()


# --------------------------------------------------------------------------- clase


def test_editar_clase_renombra_y_registra_anterior_y_nuevo(modelo):
    clase, _ = modelo.agregar_clase("Cliente")

    editada, evento = modelo.editar_clase(clase.id, nombre="  ClienteVip  ")

    assert editada is clase
    assert clase.name == "ClienteVip"
    assert isinstance(evento, ElementoModificado)
    assert (evento.elemento_id, evento.tipo, evento.contenedor_id) == (clase.id, "UmlClass", "")
    assert evento.cambios == (CambioCampo("name", "Cliente", "ClienteVip"),)


def test_editar_clase_cambia_nombre_y_abstraccion_a_la_vez(modelo):
    clase, _ = modelo.agregar_clase("Figura")

    _, evento = modelo.editar_clase(clase.id, nombre="FiguraBase", is_abstract=True)

    assert clase.is_abstract is True
    assert _cambios(evento) == {"name": ("Figura", "FiguraBase"), "is_abstract": (False, True)}


def test_editar_clase_solo_reporta_los_campos_que_cambiaron(modelo):
    clase, _ = modelo.agregar_clase("Figura")

    # Mismo nombre que ya tenía (el frontend lo reenvía al alternar abstracta): no es cambio.
    _, evento = modelo.editar_clase(clase.id, nombre="Figura", is_abstract=True)

    assert _cambios(evento) == {"is_abstract": (False, True)}


def test_editar_clase_a_su_propio_nombre_no_es_colision_ni_emite_evento(modelo):
    clase, _ = modelo.agregar_clase("Usuario")

    editada, evento = modelo.editar_clase(clase.id, nombre=" Usuario ")

    assert editada is clase
    assert evento is None


def test_editar_clase_cambiando_solo_mayusculas_si_es_un_cambio(modelo):
    clase, _ = modelo.agregar_clase("cliente")

    _, evento = modelo.editar_clase(clase.id, nombre="Cliente")

    assert _cambios(evento) == {"name": ("cliente", "Cliente")}


def test_editar_clase_rechaza_nombre_de_otra_clase_sin_distinguir_mayusculas(modelo):
    clase, _ = modelo.agregar_clase("Usuario")
    modelo.agregar_clase("Rol")

    with pytest.raises(UmlValidationError, match="Ya existe otra clase con el nombre 'rol'"):
        modelo.editar_clase(clase.id, nombre="rol")

    assert clase.name == "Usuario"


def test_editar_clase_rechaza_colision_con_otro_tipo_de_clasificador(modelo):
    clase, _ = modelo.agregar_clase("Usuario")
    modelo.interfaces.append(UmlInterface(id="i-1", name="Auditable"))

    with pytest.raises(UmlValidationError, match="Ya existe otra clase"):
        modelo.editar_clase(clase.id, nombre="Auditable")


def test_editar_clase_es_atomica_una_violacion_no_aplica_el_resto(modelo):
    clase, _ = modelo.agregar_clase("Usuario")
    modelo.agregar_clase("Rol")

    with pytest.raises(UmlValidationError):
        modelo.editar_clase(clase.id, nombre="Rol", is_abstract=True)

    assert (clase.name, clase.is_abstract) == ("Usuario", False)


def test_editar_clase_rechaza_nombre_vacio(modelo):
    clase, _ = modelo.agregar_clase("Usuario")

    with pytest.raises(UmlValidationError):
        modelo.editar_clase(clase.id, nombre="   ")

    assert clase.name == "Usuario"


def test_editar_clase_rechaza_id_inexistente_o_que_no_es_clase(modelo):
    modelo.interfaces.append(UmlInterface(id="i-1", name="Auditable"))

    with pytest.raises(ElementoNoEncontrado):
        modelo.editar_clase("no-existe", nombre="X")
    with pytest.raises(ElementoNoEncontrado):
        modelo.editar_clase("i-1", nombre="X")


# ------------------------------------------------------------------------ atributo


@pytest.fixture
def clase_con_atributos(modelo) -> UmlClass:
    clase, _ = modelo.agregar_clase("Factura")
    clase.attributes.append(UmlAttribute(id="a-num", name="numero", type="String"))
    clase.attributes.append(UmlAttribute(id="a-total", name="total", type="Double"))
    return clase


def test_editar_atributo_registra_anterior_y_nuevo_de_cada_campo(modelo, clase_con_atributos):
    clase = clase_con_atributos

    atributo, evento = modelo.editar_atributo(
        clase.id,
        "a-num",
        nombre=" codigo ",
        tipo="Integer",
        visibilidad=VisibilityKind.PUBLIC,
        is_static=True,
    )

    assert atributo is clase.attributes[0]
    assert (atributo.name, atributo.type, atributo.visibility, atributo.is_static) == (
        "codigo",
        "Integer",
        VisibilityKind.PUBLIC,
        True,
    )
    assert (evento.elemento_id, evento.tipo, evento.contenedor_id) == (
        "a-num",
        "UmlAttribute",
        clase.id,
    )
    assert _cambios(evento) == {
        "name": ("numero", "codigo"),
        "type": ("String", "Integer"),
        "visibility": (VisibilityKind.PRIVATE, VisibilityKind.PUBLIC),
        "is_static": (False, True),
    }


def test_editar_atributo_sin_cambios_efectivos_no_emite_evento(modelo, clase_con_atributos):
    _, evento = modelo.editar_atributo(
        clase_con_atributos.id, "a-num", nombre="numero", tipo="String"
    )

    assert evento is None


def test_editar_atributo_rechaza_nombre_repetido_en_la_clase_sin_distinguir_mayusculas(
    modelo, clase_con_atributos
):
    with pytest.raises(UmlValidationError, match="Ya existe otro atributo llamado 'TOTAL'"):
        modelo.editar_atributo(clase_con_atributos.id, "a-num", nombre="TOTAL", tipo="Integer")

    # Atómico: el tipo del mismo comando tampoco se aplicó.
    assert clase_con_atributos.attributes[0].type == "String"


def test_editar_atributo_permite_el_mismo_nombre_en_otra_clase(modelo, clase_con_atributos):
    otra, _ = modelo.agregar_clase("Recibo")
    otra.attributes.append(UmlAttribute(id="a-x", name="numero", type="String"))

    _, evento = modelo.editar_atributo(otra.id, "a-x", nombre="serie")

    assert _cambios(evento) == {"name": ("numero", "serie")}


def test_editar_atributo_rechaza_nombre_o_tipo_vacio(modelo, clase_con_atributos):
    with pytest.raises(UmlValidationError):
        modelo.editar_atributo(clase_con_atributos.id, "a-num", nombre="  ")
    with pytest.raises(UmlValidationError):
        modelo.editar_atributo(clase_con_atributos.id, "a-num", tipo="")


def test_editar_atributo_rechaza_clase_o_atributo_inexistente(modelo, clase_con_atributos):
    with pytest.raises(ElementoNoEncontrado, match="Clase con ID 'no-existe'"):
        modelo.editar_atributo("no-existe", "a-num", nombre="x")
    with pytest.raises(ElementoNoEncontrado, match="Atributo con ID 'no-existe'"):
        modelo.editar_atributo(clase_con_atributos.id, "no-existe", nombre="x")


# ------------------------------------------------------------------------ operación


@pytest.fixture
def clase_con_operaciones(modelo) -> UmlClass:
    clase, _ = modelo.agregar_clase("Calculadora")
    clase.operations.append(
        UmlOperation(
            id="o-calc-int", name="calcular", parameters=[UmlParameter(name="n", type="int")]
        )
    )
    clase.operations.append(
        UmlOperation(id="o-otra", name="otra", parameters=[UmlParameter(name="n", type="int")])
    )
    clase.operations.append(UmlOperation(id="o-sin-args", name="reset"))
    return clase


def test_editar_operacion_registra_anterior_y_nuevo_de_cada_campo(modelo, clase_con_operaciones):
    clase = clase_con_operaciones

    operacion, evento = modelo.editar_operacion(
        clase.id,
        "o-sin-args",
        nombre=" limpiar ",
        tipo_retorno="bool",
        visibilidad=VisibilityKind.PROTECTED,
        is_static=True,
        is_abstract=True,
    )

    assert operacion is clase.operations[2]
    assert (evento.elemento_id, evento.tipo, evento.contenedor_id) == (
        "o-sin-args",
        "UmlOperation",
        clase.id,
    )
    assert _cambios(evento) == {
        "name": ("reset", "limpiar"),
        "return_type": ("void", "bool"),
        "visibility": (VisibilityKind.PUBLIC, VisibilityKind.PROTECTED),
        "is_static": (False, True),
        "is_abstract": (False, True),
    }


def test_editar_operacion_rechaza_firma_duplicada(modelo, clase_con_operaciones):
    # "otra(int)" -> "calcular(int)" choca con la firma ya existente.
    with pytest.raises(
        UmlValidationError, match=r"Ya existe otra operación con la firma 'Calcular\(int\)'"
    ):
        modelo.editar_operacion(
            clase_con_operaciones.id, "o-otra", nombre="Calcular", tipo_retorno="int"
        )

    op = clase_con_operaciones.operations[1]
    assert (op.name, op.return_type) == ("otra", "void")  # atómico


def test_editar_operacion_permite_sobrecarga_con_distinta_firma(modelo, clase_con_operaciones):
    # "reset()" -> "calcular()" no choca con "calcular(int)": distinta lista de tipos.
    _, evento = modelo.editar_operacion(clase_con_operaciones.id, "o-sin-args", nombre="calcular")

    assert _cambios(evento) == {"name": ("reset", "calcular")}


def test_editar_operacion_sin_cambios_efectivos_no_emite_evento(modelo, clase_con_operaciones):
    _, evento = modelo.editar_operacion(
        clase_con_operaciones.id, "o-otra", nombre="otra", is_static=False
    )

    assert evento is None


def test_editar_operacion_rechaza_nombre_vacio(modelo, clase_con_operaciones):
    with pytest.raises(UmlValidationError):
        modelo.editar_operacion(clase_con_operaciones.id, "o-otra", nombre="  ")


def test_editar_operacion_rechaza_clase_u_operacion_inexistente(modelo, clase_con_operaciones):
    with pytest.raises(ElementoNoEncontrado, match="Clase con ID 'no-existe'"):
        modelo.editar_operacion("no-existe", "o-otra", nombre="x")
    with pytest.raises(ElementoNoEncontrado, match="Operación con ID 'no-existe'"):
        modelo.editar_operacion(clase_con_operaciones.id, "no-existe", nombre="x")
