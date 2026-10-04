"""Catálogo cerrado de categorías y subcategorías de cultura de paz."""

import re
import unicodedata


CATEGORIES = (
    {
        "code": "CCP",
        "name": "Concepción docente de la cultura de paz",
        "items": (
            ("CCP1", "Valores fundamentales de la cultura de paz"),
            ("CCP2", "Principios que orientan la cultura de paz"),
            ("CCP3", "Importancia de fomentar la cultura de paz desde edades tempranas"),
        ),
    },
    {
        "code": "DCP",
        "name": "Desarrollo infantil y cultura de paz",
        "items": (
            ("DCP1", "Acciones de la niñez en relación con la cultura de paz"),
            ("DCP2", "Influencia de la etapa de desarrollo en la promoción de una cultura de paz"),
        ),
    },
    {
        "code": "RCP",
        "name": "Rol docente en la promoción de la cultura de paz",
        "items": (
            ("RCP1", "Mediación pedagógica"),
            ("RCP2", "Intervención docente ante el conflicto"),
            ("RCP3", "Estrategias pedagógicas concretas"),
            ("RCP4", "Ambientes físicos"),
            ("RCP5", "Ambientes psicosociales"),
        ),
    },
    {
        "code": "FCP",
        "name": "Familia en la construcción de la cultura de paz",
        "items": (
            ("FCP1", "Comunicación docente-familias"),
            ("FCP2", "Dinámicas familiares"),
        ),
    },
    {
        "code": "LCP",
        "name": "Limitaciones en la implementación de una cultura de paz",
        "items": (
            ("LCP1", "Formación docente"),
            ("LCP2", "Elementos disruptivos"),
            ("LCP3", "Disposiciones institucionales"),
        ),
    },
    {
        "code": "FPCP",
        "name": "Factores promotores de una cultura de paz",
        "items": (
            ("FPCP1", "Puntos de mejora"),
            ("FPCP2", "Elementos institucionales favorecedores para la promoción de la cultura de paz"),
        ),
    },
)


def normalized_name(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def catalog_options():
    options = []
    for category in CATEGORIES:
        codes = [code for code, _ in category["items"]]
        options.append({"type": "category", "value": category["code"],
                        "name": category["name"], "codes": codes})
        options.extend({"type": "subcategory", "value": code, "name": name, "codes": [code]}
                       for code, name in category["items"])
    return options


def resolve_query(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Selecciona o escribe una categoría para buscar.")
    raw = value.strip()
    wrapped = re.fullmatch(r"\(\s*([^()]*)\s*\)", raw)
    if wrapped:
        raw = wrapped.group(1).strip()
    compact = re.sub(r"[\s_-]+", "", raw).upper()
    name = normalized_name(raw)
    for option in catalog_options():
        if compact == option["value"] or name == normalized_name(option["name"]):
            return {"query": option["value"], "label": option["name"],
                    "codes": option["codes"], "type": option["type"]}
    allowed = ", ".join(category["code"] for category in CATEGORIES)
    raise ValueError(f"Búsqueda no reconocida. Usa una categoría ({allowed}), un subcódigo o un nombre del catálogo.")
