"""
Parser explícito de multiplicidades legacy a MultiplicityRange V2.
"""

from typing import Tuple
import re

from ..model import MultiplicityRange


class LegacyMultiplicityParser:
    """
    Parsea cadenas textuales de cardinalidad hacia la estructura formal MultiplicityRange.
    Lanza ValueError explícito ante formatos no reconocidos para evitar suposiciones silenciosas.
    """

    @classmethod
    def parse(cls, label: str, default_if_empty: bool = False) -> MultiplicityRange:
        if not label or not label.strip():
            if default_if_empty:
                # Regla de fallback documentada: si está vacía se mapea a '*'
                return MultiplicityRange(lower=0, upper=None)
            raise ValueError("Etiqueta de multiplicidad vacía.")

        text = label.strip()

        # 1. Comodines directos
        if text in ["*", "0..*"]:
            return MultiplicityRange(lower=0, upper=None)

        if text in ["1", "1..1"]:
            return MultiplicityRange(lower=1, upper=1)

        if text == "0..1":
            return MultiplicityRange(lower=0, upper=1)

        if text == "1..*":
            return MultiplicityRange(lower=1, upper=None)

        # 2. Rangos explícitos "lower..upper" o "lower..*"
        range_match = re.match(r"^(\d+)\.\.(\*|\d+)$", text)
        if range_match:
            lower = int(range_match.group(1))
            upper_str = range_match.group(2)
            upper = None if upper_str == "*" else int(upper_str)
            return MultiplicityRange(lower=lower, upper=upper)

        # 3. Entero único positivo "N" -> [N, N]
        if text.isdigit():
            val = int(text)
            return MultiplicityRange(lower=val, upper=val)

        # 4. Notaciones algebraicas legacy comunes en diagramación informal: 'n', 'm' -> '*'
        if text.lower() in ["n", "m"]:
            return MultiplicityRange(lower=0, upper=None)

        raise ValueError(
            f"Formato de multiplicidad no reconocido: '{label}'. Formatos válidos: '1', '*', '0..1', '0..*', '1..*', 'N..M'."
        )
