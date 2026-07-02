"""Tour Script service for AutoMind AI Platform.

Provides serialization, parsing, and validation of Tour_Script JSON.
"""

import json
from typing import Any

from pydantic import ValidationError

from app.schemas.tour_script import TourScript


def serialize_tour_script(tour: TourScript) -> str:
    """Serialize a TourScript model to a JSON string.

    Args:
        tour: A valid TourScript model instance.

    Returns:
        JSON string representation including schema_version.
    """
    return tour.model_dump_json()


def parse_tour_script(json_str: str) -> TourScript:
    """Parse a JSON string into a TourScript model.

    Args:
        json_str: A JSON string representing a tour script.

    Returns:
        A validated TourScript model instance.

    Raises:
        ValidationError: If the JSON does not conform to the schema.
    """
    return TourScript.model_validate_json(json_str)


def validate_tour_script(json_str: str) -> list[dict[str, Any]]:
    """Validate a JSON string against the TourScript schema.

    Returns a list of error dicts if validation fails, or an empty list
    if the JSON is valid.

    Args:
        json_str: A JSON string to validate.

    Returns:
        List of error dicts, each with 'path', 'constraint', and 'expected' keys.
        Empty list if valid.
    """
    try:
        TourScript.model_validate_json(json_str)
        return []
    except ValidationError as e:
        errors: list[dict[str, Any]] = []
        for error in e.errors():
            loc = error.get("loc", ())
            path = ".".join(str(part) for part in loc) if loc else "<root>"
            error_type = error.get("type", "unknown")
            msg = error.get("msg", "")

            # Map pydantic error types to constraint descriptions
            constraint = _map_error_type_to_constraint(error_type)
            expected = msg

            errors.append({
                "path": path,
                "constraint": constraint,
                "expected": expected,
            })
        return errors
    except json.JSONDecodeError:
        return [{
            "path": "<root>",
            "constraint": "valid_json",
            "expected": "Valid JSON document",
        }]


def _map_error_type_to_constraint(error_type: str) -> str:
    """Map pydantic error type to a human-readable constraint name."""
    mapping = {
        "missing": "required_field",
        "string_type": "type_string",
        "int_type": "type_integer",
        "int_parsing": "type_integer",
        "list_type": "type_list",
        "bool_type": "type_boolean",
        "model_type": "type_object",
        "json_invalid": "valid_json",
        "value_error": "value_constraint",
        "extra_forbidden": "no_extra_fields",
    }
    return mapping.get(error_type, error_type)
