"""
core/uml_domain/exceptions.py

Taxonomía canónica de excepciones del dominio UML.
Prohibido usar raise Exception("...") genérico en el proyecto.
"""


class UmlDomainError(Exception):
    """Base de toda excepción del dominio UML."""


class UmlValidationError(UmlDomainError):
    """Una operación viola una regla de consistencia del modelo UML."""


class ElementoNoEncontrado(UmlDomainError):
    """Se referenció un elemento (clase, relación, atributo) que no existe."""


class CanvasNoEncontrado(UmlDomainError):
    """Se referenció un lienzo que no existe o no es accesible."""


class ConcurrentEditConflict(UmlDomainError):
    """Reservado para CU5 — conflicto de edición concurrente."""


class UnsupportedGenerationFeature(UmlDomainError):
    """Reservado para CU10/CU11 — el modelo usa algo que el generador no soporta."""
