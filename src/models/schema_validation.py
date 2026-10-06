"""
ThemeSync — Pre-Orchestration Schema Validation
================================================
Chapter 3, p.44, "Validation of Hybrid Visual DNA Correctness": the
user-defined typographic parameters (font family, font weight, baseline
geometric sizing) are validated against a rigid JSON Schema before the GNN
or the Cassowary solver run, and a payload that violates it rejects the
initialization — e.g. a font weight that isn't a valid integer, or a
baseline size that would exceed the viewport. The content payload is
checked the same way against the target format's variable schema (every
variable present, each within its max_characters).

Figure 3's State Timeline logs the result ("Schema Validation") as part of
the first state.
"""

import jsonschema

FONT_WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900]


def typography_schema(canvas_w: float, canvas_h: float) -> dict:
    """JSON Schema for the administrative typography. The baseline size may
    not exceed 15% of the viewport's shorter side: a base size is the
    certificate title's size, and anything larger cannot fit the format."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ThemeSync administrative typography",
        "type": "object",
        "required": ["family", "weight", "base_size"],
        "properties": {
            "family":    {"type": "string", "minLength": 1, "maxLength": 200},
            "weight":    {"type": "integer", "enum": FONT_WEIGHTS},
            "base_size": {"type": "number", "minimum": 8,
                          "maximum": round(0.15 * min(canvas_w, canvas_h), 1)},
        },
        "additionalProperties": False,
    }


def content_schema(payload_meta: dict) -> dict:
    """JSON Schema for a content payload, derived from the format's
    variable_schema: every variable (repeating groups as {{Name}}_0...) is
    required, a string, and within its max_characters."""
    properties, required = {}, []
    for var, spec in payload_meta.get("variable_schema", {}).items():
        keys = ([f"{var}_{i}" for i in range(spec.get("instantiation_count", 1))]
                if spec.get("instantiation_count", 1) > 1 else [var])
        for key in keys:
            prop = {"type": "string"}
            if spec.get("max_characters"):
                prop["maxLength"] = int(spec["max_characters"])
            properties[key] = prop
            required.append(key)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"ThemeSync content payload ({payload_meta.get('domain_context', 'layout')})",
        "type": "object",
        "required": required,
        "properties": properties,
    }


def _errors(instance, schema) -> list:
    validator = jsonschema.Draft202012Validator(schema)
    out = []
    for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in e.path) or "(payload)"
        out.append(f"{where}: {e.message}")
    return out


def validate_typography(typography: dict, canvas_w: float, canvas_h: float) -> dict:
    """{"valid": bool, "errors": [...], "schema": name} for the typography."""
    errors = _errors(typography, typography_schema(canvas_w, canvas_h))
    return {"valid": not errors, "errors": errors, "schema": "administrative typography"}


def validate_content(content: dict, payload_meta: dict) -> dict:
    """{"valid": bool, "errors": [...], "schema": name} for a content payload."""
    errors = _errors(content, content_schema(payload_meta))
    return {"valid": not errors, "errors": errors, "schema": "content payload"}
