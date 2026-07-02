"""Property-based tests for Tour Script schema and validation.

Feature: automind-ai-platform
Tests Properties 9, 10, and 11 for Tour Script serialization,
validation error specificity, and unknown field tolerance.
"""

import json
import string

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from app.schemas.tour_script import (
    Dimensions,
    Feature,
    Metadata,
    Narration,
    Room,
    SourceAssets,
    TourScript,
    Transition,
    Visuals,
)
from app.services.tour_script_service import (
    parse_tour_script,
    serialize_tour_script,
    validate_tour_script,
)


# --- Strategies for generating valid Tour Script objects ---

def st_narration():
    """Generate valid Narration objects."""
    return st.builds(
        Narration,
        text=st.text(min_size=1, max_size=30, alphabet=string.ascii_letters + " "),
        duration_seconds=st.integers(min_value=1, max_value=300),
        language=st.sampled_from(["en", "hi", "mr", "ta"]),
    )


def st_dimensions():
    """Generate valid Dimensions objects."""
    return st.builds(
        Dimensions,
        width=st.integers(min_value=1, max_value=7680),
        height=st.integers(min_value=1, max_value=4320),
    )


def st_visuals():
    """Generate valid Visuals objects."""
    return st.builds(
        Visuals,
        primary_image_url=st.just("https://cdn.example.com/img.jpg"),
        thumbnail_url=st.one_of(
            st.none(),
            st.just("https://cdn.example.com/thumb.jpg"),
        ),
        labels=st.lists(st.sampled_from(["sofa", "window", "light", "floor", "wall"]), min_size=0, max_size=3),
        dimensions=st.one_of(st.none(), st_dimensions()),
    )


def st_feature():
    """Generate valid Feature objects."""
    return st.builds(
        Feature,
        name=st.sampled_from(["Marble Flooring", "Bay Windows", "LED Lights", "Oak Cabinets"]),
        category=st.sampled_from(["flooring", "windows", "lighting", "kitchen", "bathroom", "garden"]),
    )


def st_transition():
    """Generate valid Transition objects."""
    return st.builds(
        Transition,
        type=st.sampled_from(["slide_left", "slide_right", "fade", "zoom"]),
        duration_ms=st.integers(min_value=100, max_value=1000),
    )


def st_room(index: int | None = None):
    """Generate valid Room objects."""
    room_types = ["living_room", "bedroom", "kitchen", "bathroom", "balcony", "study"]
    idx = st.just(index) if index is not None else st.integers(min_value=0, max_value=20)
    return st.builds(
        Room,
        index=idx,
        id=st.sampled_from(["room_a", "room_b", "room_c", "room_d", "room_e", "room_f", "room_g", "room_h"]),
        name=st.sampled_from(["Living Room", "Bedroom", "Kitchen", "Bathroom", "Balcony", "Study"]),
        room_type=st.sampled_from(room_types),
        narration=st_narration(),
        visuals=st.one_of(st.none(), st_visuals()),
        features=st.lists(st_feature(), min_size=0, max_size=3),
        transition=st.one_of(st.none(), st_transition()),
    )


def st_source_assets():
    """Generate valid SourceAssets objects."""
    return st.builds(
        SourceAssets,
        images_processed=st.one_of(st.none(), st.integers(min_value=0, max_value=100)),
        pdfs_processed=st.one_of(st.none(), st.integers(min_value=0, max_value=10)),
    )


def st_metadata():
    """Generate valid Metadata objects."""
    return st.builds(
        Metadata,
        generated_at=st.just("2024-01-15T10:00:00Z"),
        pipeline_version=st.sampled_from(["1.0.0", "1.1.0", "2.0.0"]),
        source_assets=st.one_of(st.none(), st_source_assets()),
    )


def st_tour_script():
    """Generate valid TourScript objects."""
    return st.integers(min_value=1, max_value=5).flatmap(
        lambda n: st.builds(
            TourScript,
            schema_version=st.just("1.0.0"),
            project_id=st.uuids().map(str),
            project_name=st.sampled_from(["Sunshine Heights", "Park View", "Green Valley", "Sky Tower"]),
            total_rooms=st.just(n),
            estimated_duration_seconds=st.integers(min_value=30, max_value=600),
            rooms=st.lists(st_room(), min_size=n, max_size=n),
            metadata=st.one_of(st.none(), st_metadata()),
        )
    )


# --- Property 9: Tour Script Serialization Round-Trip ---

@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(tour=st_tour_script())
def test_property_9_tour_script_round_trip(tour: TourScript):
    """Property 9: Tour Script Serialization Round-Trip

    For any valid TourScript object, serializing to JSON and parsing
    the result back produces an object deep-equal to the original.

    **Validates: Requirements 15.1, 15.2, 15.3**
    """
    # Serialize to JSON
    json_str = serialize_tour_script(tour)

    # Parse back
    parsed = parse_tour_script(json_str)

    # Deep equality check
    assert parsed == tour, (
        f"Round-trip failed.\nOriginal: {tour}\nParsed: {parsed}"
    )

    # Also verify serialize(parse(serialize(obj))) == serialize(obj)
    re_serialized = serialize_tour_script(parsed)
    assert re_serialized == json_str


# --- Property 10: Tour Script Validation Error Specificity ---

@st.composite
def st_invalid_tour_script_json(draw):
    """Generate Tour_Script JSON with schema violations."""
    violation_type = draw(st.sampled_from([
        "missing_required_field",
        "wrong_type_score",
        "wrong_type_rooms",
        "missing_room_field",
        "wrong_narration_type",
    ]))

    # Start with a valid base
    base = {
        "schema_version": "1.0.0",
        "project_id": "test-project-id",
        "project_name": "Test Project",
        "total_rooms": 1,
        "estimated_duration_seconds": 120,
        "rooms": [
            {
                "index": 0,
                "id": "room_1",
                "name": "Living Room",
                "room_type": "living_room",
                "narration": {
                    "text": "Welcome",
                    "duration_seconds": 30,
                    "language": "en",
                },
                "features": [],
            }
        ],
    }

    if violation_type == "missing_required_field":
        # Remove a required top-level field
        field = draw(st.sampled_from(["schema_version", "project_id", "project_name", "total_rooms", "rooms"]))
        del base[field]
    elif violation_type == "wrong_type_score":
        # Set total_rooms to a string instead of int
        base["total_rooms"] = "not_a_number"
    elif violation_type == "wrong_type_rooms":
        # Set rooms to a string instead of list
        base["rooms"] = "not_a_list"
    elif violation_type == "missing_room_field":
        # Remove a required room field
        field = draw(st.sampled_from(["index", "id", "name", "room_type", "narration"]))
        del base["rooms"][0][field]
    elif violation_type == "wrong_narration_type":
        # Set narration to a string
        base["rooms"][0]["narration"] = "not_an_object"

    return json.dumps(base)


@settings(max_examples=50)
@given(invalid_json=st_invalid_tour_script_json())
def test_property_10_validation_error_specificity(invalid_json: str):
    """Property 10: Tour Script Validation Error Specificity

    For any Tour_Script JSON that does not conform to the schema,
    the validation error includes JSON path, constraint violated,
    and expected format.

    **Validates: Requirements 15.4**
    """
    errors = validate_tour_script(invalid_json)

    # Must have at least one error
    assert len(errors) > 0, f"Expected validation errors for: {invalid_json}"

    for error in errors:
        # Each error must have path, constraint, and expected
        assert "path" in error, f"Error missing 'path': {error}"
        assert "constraint" in error, f"Error missing 'constraint': {error}"
        assert "expected" in error, f"Error missing 'expected': {error}"

        # Path should be a non-empty string
        assert isinstance(error["path"], str) and len(error["path"]) > 0
        # Constraint should be a non-empty string
        assert isinstance(error["constraint"], str) and len(error["constraint"]) > 0
        # Expected should be a non-empty string
        assert isinstance(error["expected"], str) and len(error["expected"]) > 0


# --- Property 11: Tour Script Unknown Field Tolerance ---

@st.composite
def st_valid_json_with_extras(draw):
    """Generate valid Tour_Script JSON with random additional fields."""
    tour = draw(st_tour_script())
    json_str = serialize_tour_script(tour)
    data = json.loads(json_str)

    # Add random extra fields at top level
    extra_key = draw(st.sampled_from(["extra_field", "bonus_data", "unknown_attr", "custom_flag", "internal_id"]))
    assume(extra_key not in data)
    extra_value = draw(st.one_of(
        st.just("extra_value"),
        st.integers(min_value=0, max_value=1000),
        st.booleans(),
    ))
    data[extra_key] = extra_value

    # Optionally add extra field to a room
    if data["rooms"]:
        room_extra_key = draw(st.sampled_from(["extra_room_field", "hidden_data", "debug_info"]))
        existing_room_keys = set(data["rooms"][0].keys())
        assume(room_extra_key not in existing_room_keys)
        data["rooms"][0][room_extra_key] = "extra_value"

    return json.dumps(data), tour


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(data=st_valid_json_with_extras())
def test_property_11_unknown_field_tolerance(data: tuple[str, TourScript]):
    """Property 11: Tour Script Unknown Field Tolerance

    For any valid Tour_Script JSON with additional unknown fields,
    parsing succeeds without error and the resulting object does
    not contain the unrecognized fields.

    **Validates: Requirements 15.5**
    """
    json_with_extras, original_tour = data

    # Parsing should succeed
    parsed = parse_tour_script(json_with_extras)

    # Result should be valid and match the original (without extras)
    assert parsed == original_tour, (
        f"Parsed result doesn't match original.\n"
        f"Input with extras: {json_with_extras}\n"
        f"Parsed: {parsed}\n"
        f"Original: {original_tour}"
    )

    # Verify no extra fields in the serialized output
    serialized = serialize_tour_script(parsed)
    parsed_dict = json.loads(serialized)
    original_dict = json.loads(serialize_tour_script(original_tour))
    assert parsed_dict == original_dict
