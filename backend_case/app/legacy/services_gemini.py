import json
import os
import re
from uuid import uuid4

import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent"


def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def call_gemini(prompt: str, model_context: dict | None = None):
    GEMINI_API_KEY = get_gemini_api_key()

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    # Detectar si la instrucción pide algo distinto de crear un modelo nuevo desde cero
    # (renombrar, agregar/editar/eliminar miembros o relaciones sobre clases YA existentes).
    operation_keywords = [
        "cambies",
        "cambiar",
        "cambia",
        "renombra",
        "renombrar",
        "edites",
        "edita",
        "editar",
        "modifiques",
        "modifica",
        "modificar",
        "actualices",
        "actualizar",
        "actualiza",
        "agrega",
        "agregar",
        "agregale",
        "agrégale",
        "añadir",
        "añade",
        "sumale",
        "súmale",
        "suma",
        "eliminar",
        "elimina",
        "borra",
        "borrar",
        "quitar",
        "quita",
        "remover",
        "remueve",
        "sacar",
        "saca",
        "delete",
        "remove",
    ]
    is_operations_request = any(keyword in prompt.lower() for keyword in operation_keywords)

    if is_operations_request:
        # Prompt unificado (CU6): cualquier instrucción sobre un modelo YA existente
        # (renombrar, agregar/editar/eliminar miembros, agregar/editar/eliminar relaciones)
        # devuelve una lista de operaciones atómicas identificadas por NOMBRE, nunca por id
        # -- Gemini no conoce los ids reales del lienzo persistido.
        context_json = json.dumps(
            model_context or {"classes": [], "relationships": []}, indent=2, ensure_ascii=False
        )
        prompt_text = f"""
Analiza la siguiente instrucción sobre un modelo UML QUE YA EXISTE (ver más abajo) y devolvé
UN SOLO JSON con la lista de operaciones necesarias para aplicarla, en el orden en que deben
ejecutarse.

IMPORTANTE: Todas las clases, atributos, métodos y relaciones que edites o elimines YA EXISTEN
en el modelo actual. Identificalos por su NOMBRE EXACTO tal como aparece ahí -- nunca inventes
ni uses ids, la aplicación los resuelve por nombre contra el modelo real.

Formato de respuesta:
```json
{{
  "operations": [
    {{"action": "rename_class", "target": "NombreActual", "newName": "NombreNuevo"}},
    {{"action": "add_attribute", "target": "NombreClase", "name": "atributo", "type": "tipo"}},
    {{"action": "update_attribute", "target": "NombreClase", "attribute": "atributoActual",
     "newName": "nuevoNombre", "newType": "nuevoTipo"}},
    {{"action": "delete_attribute", "target": "NombreClase", "attribute": "atributoAEliminar"}},
    {{"action": "add_operation", "target": "NombreClase", "name": "metodo",
     "returnType": "tipoRetorno"}},
    {{"action": "delete_operation", "target": "NombreClase", "operation": "metodoAEliminar"}},
    {{"action": "delete_class", "target": "NombreClase"}},
    {{"action": "add_relationship", "sourceClass": "ClaseA", "targetClass": "ClaseB",
     "type": "ASSOCIATION | GENERALIZATION | AGGREGATION | COMPOSITION | DEPENDENCY"}},
    {{"action": "delete_relationship", "sourceClass": "ClaseA", "targetClass": "ClaseB"}},
    {{"action": "update_relationship_type", "sourceClass": "ClaseA", "targetClass": "ClaseB",
     "newType": "ASSOCIATION | GENERALIZATION | AGGREGATION | COMPOSITION | DEPENDENCY"}},
    {{"action": "update_multiplicity", "sourceClass": "ClaseA", "targetClass": "ClaseB",
     "newMultiplicity": "0..* | 1 | 0..1 | 1..*"}}
  ]
}}
```

REGLAS IMPORTANTES:
- Usá EXCLUSIVAMENTE los nombres de clases/atributos/métodos que aparecen en el "Modelo UML
  actual" de abajo para "target", "attribute", "operation", "sourceClass" y "targetClass".
- Si la instrucción cambia el nombre de una clase y LUEGO hace referencia a esa misma clase en
  otra operación de la misma lista, usá el nombre NUEVO en las operaciones siguientes -- se
  aplican en el orden en que las devolvés.
- En "update_attribute" incluí solo "newName" y/o "newType", según lo que realmente cambió.
- No uses ninguna acción fuera de las listadas arriba.
- Si la instrucción pide crear un modelo completamente nuevo desde cero (sin referirse a ninguna
  clase existente), NO es una operación -- no apliquen esta forma de respuesta a ese caso.
- NO devuelvas nada más, solo el JSON.

Modelo UML actual del lienzo (nombres reales a usar como referencia):
{context_json}

Instrucción del usuario:
{prompt}
"""
    else:
        # Prompt normal - devolver un solo JSON
        prompt_text = f"""
Convierte el siguiente prompt en un JSON UML válido. 
El JSON **debe seguir exactamente** esta estructura:

{{
  "classes": [
    {{
      "id": "uuid",
      "name": "NombreClase",
      "attributes": [
        {{"name": "atributo", "type": "tipo"}}
      ],
      "methods": [
        {{"name": "metodo", "parameters": "", "returnType": ""}}
      ]
    }}
  ],
  "relationships": [
    {{
      "id": "uuid",
      "type": "association | generalization | aggregation | composition | dependency",
      "sourceId": "uuid",
      "targetId": "uuid",
      "labels": ["1..*", "1"]
    }}
  ]
}}

Usa UUIDs generados aleatoriamente como 'id'.
NO devuelvas nada más, solo el JSON.

Prompt del usuario:
{prompt}
"""

    data = {"contents": [{"parts": [{"text": prompt_text}]}]}

    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()

    try:
        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        return text_output
    except (KeyError, IndexError):
        return '{"error": "No se pudo parsear la respuesta de Gemini"}'


def call_gemini_analysis(prompt: str):
    GEMINI_API_KEY = get_gemini_api_key()

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"""
Analiza este modelo UML y responde SOLO en formato JSON.

Estructura de salida obligatoria:
{{
  "validas": [
    {{
      "relacion": "Texto corto con tipo y tablas",
      "razon": "Por qué es válida"
    }}
  ],
  "errores": [
    {{
      "relacion": "Texto corto con tipo y tablas",
      "problema": "Qué está mal",
      "sugerencia": "Cómo corregirlo"
    }}
  ]
}}

No escribas explicaciones fuera del JSON.
Prompt:
{prompt}
"""
                    }
                ]
            }
        ]
    }

    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()

    try:
        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        return text_output
    except (KeyError, IndexError):
        return '{"error": "No se pudo parsear la respuesta de Gemini"}'


def _edge_to_relationship_type(edge):
    """
    Determina el tipo de relación UML a partir de los rasgos visuales detectados por Gemini.
    Retorna (tipo_relacion, posicion_del_simbolo)
    """
    head = edge.get("head", {})
    tail = edge.get("tail", {})
    line = edge.get("line", {})

    head_shape = head.get("shape")
    head_fill = head.get("fill")
    head_size = head.get("size")
    tail_shape = tail.get("shape")
    tail_diamond = tail.get("diamond")
    tail_fill = tail.get("fill")
    line_style = line.get("style")

    # Verificar rombos en TAIL (composition/aggregation)
    if tail_diamond == "black" or (tail_shape == "diamond" and tail_fill == "black"):
        return "composition", "tail"
    if tail_diamond == "white" or (
        tail_shape == "diamond" and (tail_fill in ["white", "none", None])
    ):
        return "aggregation", "tail"

    # Verificar rombos en HEAD (composition/aggregation)
    if head_shape == "diamond":
        if head_fill == "solid" or head_fill == "black":
            return "composition", "head"
        else:
            return "aggregation", "head"

    # Verificar línea punteada (dependency)
    if line_style == "dashed":
        return "dependency", "none"

    # Verificar triángulos en HEAD (generalization)
    if head_shape == "triangle":
        if head_fill == "none" or head_fill == "white" or head_size == "large":
            return "generalization", "head"

    # Verificar triángulos en TAIL (generalization)
    if tail_shape == "triangle":
        if tail_fill == "none" or tail_fill == "white":
            return "generalization", "tail"

    # Por defecto: association
    return "association", "none"


def _map_edges_to_relationships(parsed_json):
    """
    Convierte los edges detectados por Gemini en relaciones UML bien orientadas.
    Corrige dirección si los símbolos están en el lado contrario.
    """
    nodes = parsed_json.get("nodes", [])
    edges = parsed_json.get("edges_raw", [])

    # Crear IDs por nombre
    name_to_id = {n.get("name"): (n.get("id") or str(uuid4())) for n in nodes}

    classes = [
        {
            "id": name_to_id[n.get("name")],
            "name": n.get("name"),
            "attributes": n.get("attributes", []),
            "methods": n.get("methods", []),
        }
        for n in nodes
    ]

    relationships = []
    seen_relationships = set()
    relationship_by_key = {}

    for e in edges:
        rel_type, symbol_position = _edge_to_relationship_type(e)
        src = e.get("sourceName")
        tgt = e.get("targetName")
        labels = e.get("labels", [])

        if not src or not tgt:
            continue

        if rel_type == "aggregation":
            if symbol_position == "head":
                src, tgt = tgt, src
        elif rel_type == "composition":
            pass
        elif rel_type == "generalization":
            if symbol_position == "tail":
                src, tgt = tgt, src

        src_id = name_to_id.get(src)
        tgt_id = name_to_id.get(tgt)

        rel_key = f"{src_id}-{tgt_id}-{rel_type}"
        rel_key_reverse = f"{tgt_id}-{src_id}-{rel_type}"

        clean_labels = [
            label for label in labels if label is not None and label != "null" and label != ""
        ]

        if rel_key in seen_relationships:
            prev_rel = relationship_by_key.get(rel_key)
            if prev_rel and not prev_rel["labels"] and clean_labels:
                prev_rel["labels"] = clean_labels
            continue

        if rel_key_reverse in seen_relationships:
            prev_rel = relationship_by_key.get(rel_key_reverse)
            if prev_rel and not prev_rel["labels"] and clean_labels:
                prev_rel["labels"] = clean_labels
            continue

        seen_relationships.add(rel_key)

        new_rel = {
            "id": e.get("id") or str(uuid4()),
            "type": rel_type,
            "sourceId": src_id,
            "targetId": tgt_id,
            "labels": clean_labels,
        }
        relationships.append(new_rel)
        relationship_by_key[rel_key] = new_rel

    return {"classes": classes, "relationships": relationships}


def call_gemini_from_image(image_base64: str, mime_type: str = "image/png"):
    """
    Envía una imagen UML a Gemini y devuelve un JSON estructurado con clases y relaciones.
    """
    GEMINI_API_KEY = get_gemini_api_key()
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    prompt_text = """
Analiza cuidadosamente la imagen de un **diagrama de clases UML**.

🎯 **OBJETIVO**: Identificar TODAS las clases y relaciones visibles.

**PASO 1: Identificar clases**
Detecta todos los rectángulos que representan clases con:
- Nombre de la clase (en la parte superior)
- Atributos en formato `nombre:tipo`
- Métodos en formato `nombre():tipoRetorno` o `nombre(params):tipoRetorno`

**PASO 2: Identificar relaciones**
Para CADA línea/conector entre clases, describe:

📍 **Símbolos en los extremos**:
- **Triángulo blanco/vacío GRANDE** → indica HERENCIA (generalization)
- **Rombo blanco/vacío** → indica AGREGACIÓN (aggregation)
- **Rombo negro/relleno** → indica COMPOSICIÓN (composition)
- **Flecha simple** o **ningún símbolo** → indica ASOCIACIÓN (association)
- **Línea punteada** → indica DEPENDENCIA (dependency)

📍 **Ubicación del símbolo**: 
- Si el símbolo (triángulo, rombo) está en el EXTREMO DERECHO o SUPERIOR de la línea → ese es el HEAD (destino)
- Si está en el EXTREMO IZQUIERDO o INFERIOR → ese es el TAIL (origen)

📍 **Etiquetas de cardinalidad**: Busca números cerca de los extremos como "1", "0..1", "1..*", "*"
   - Si una línea tiene etiquetas en AMBOS extremos (ej: "1..*" cerca de Persona y "0..1" cerca de Perro)
   - Reporta las etiquetas como: ["1..*", "0..1"]
   - NO crees dos relaciones separadas, es UNA SOLA relación bidireccional

**REGLAS CRÍTICAS**:
1. NO inventes relaciones que no existen visualmente
2. Una línea = UNA relación (incluso si tiene etiquetas en ambos extremos)
3. Si una línea tiene múltiples etiquetas, inclúyelas TODAS en el array "labels"
4. Cuenta las líneas FÍSICAS en la imagen, NO las etiquetas
5. Reporta EXACTAMENTE lo que ves

⚠️ **FORMATO DE SALIDA** (JSON exacto sin explicaciones):

{
  "nodes": [
    {
      "id": "uuid1",
      "name": "NombreClase",
      "attributes": [
        {"name": "atributo", "type": "tipo"}
      ],
      "methods": [
        {"name": "metodo", "parameters": "", "returnType": "tipo"}
      ]
    }
  ],
  "edges_raw": [
    {
      "id": "edge-uuid1",
      "sourceName": "ClaseOrigen",
      "targetName": "ClaseDestino",
      "head": {
        "shape": "triangle|diamond|none",
        "fill": "solid|none|white|black",
        "size": "small|large|medium"
      },
      "tail": {
        "shape": "triangle|diamond|none",
        "diamond": "none|white|black",
        "fill": "solid|none|white|black"
      },
      "line": {
        "style": "solid|dashed"
      },
      "labels": ["etiqueta_extremo1", "etiqueta_extremo2"]
    }
  ]
}

**EJEMPLO IMPORTANTE**:
Si ves una línea entre Persona y Perro con "1..*" cerca de Persona y "0..1" cerca de Perro:
```json
{
  "id": "edge-1",
  "sourceName": "Persona",
  "targetName": "Perro",
  "labels": ["1..*", "0..1"]
}
```
NO crees dos edges separadas. Es una sola línea física.

**IMPORTANTE**: 
- sourceName y targetName deben ser nombres exactos de clases detectadas
- Para cada relación, identifica CLARAMENTE qué símbolo está en qué extremo
- NO uses "unknown" a menos que sea completamente imposible determinarlo
- Cuenta líneas físicas, no etiquetas

NO escribas texto fuera del JSON.
"""

    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                ]
            }
        ]
    }

    try:
        response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
        response.raise_for_status()
        result = response.json()

        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        text_output = re.sub(r"^```json\s*|\s*```$", "", text_output.strip(), flags=re.MULTILINE)
        parsed = json.loads(text_output)

        uml_json = _map_edges_to_relationships(parsed)
        return uml_json

    except Exception as e:
        return {"error": str(e)}
