"""Bounded literal text substitution; no code, attributes or expressions."""
from string import Formatter

FIELDS = frozenset({"icon", "condition", "high", "low", "unit", "location", "date", "details", "title"})

def validate_template(value):
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError("Template must contain at most 2000 characters")
    for _, field, spec, conversion in Formatter().parse(value):
        if field is not None and (field not in FIELDS or spec or conversion):
            raise ValueError("Use only the documented plain placeholders")
    return value

def render(value, fields, fallback):
    if not value:
        return fallback
    try:
        return validate_template(value).format_map(fields)
    except (ValueError, KeyError, TypeError):
        return fallback
