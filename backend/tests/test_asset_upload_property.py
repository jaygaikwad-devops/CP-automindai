"""Property-based tests for asset upload validation.

**Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5, 17.11**

Uses hypothesis to generate random file metadata and verify that
the validation function accepts uploads if and only if format matches,
size is within limit, and count is not exceeded.
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.services.asset_validation import (
    ALLOWED_MIMES,
    MAX_COUNT,
    MAX_SIZE_BYTES,
    validate_asset_upload,
)


# --- Strategies ---

# Valid asset types
asset_type_strategy = st.sampled_from(["image", "video", "brochure", "floor_plan"])

# Valid MIME types per asset_type
valid_mime_for_type = {
    "image": st.sampled_from(["image/jpeg", "image/png"]),
    "video": st.just("video/mp4"),
    "brochure": st.just("application/pdf"),
    "floor_plan": st.sampled_from(["image/jpeg", "image/png", "application/pdf"]),
}

# Invalid MIME types (ones that don't match any category)
invalid_mimes = st.sampled_from([
    "text/plain",
    "application/json",
    "image/gif",
    "video/avi",
    "application/zip",
    "audio/mp3",
    "image/webp",
    "video/webm",
])


@st.composite
def valid_upload_metadata(draw):
    """Generate metadata for a valid upload (format matches, size OK, count OK)."""
    asset_type = draw(asset_type_strategy)
    mime_type = draw(valid_mime_for_type[asset_type])
    max_size = MAX_SIZE_BYTES[asset_type]
    # Size between 1 byte and max size
    file_size = draw(st.integers(min_value=1, max_value=max_size))
    max_count = MAX_COUNT[asset_type]
    # Existing count from 0 to max_count - 1 (so there's room for one more)
    existing_count = draw(st.integers(min_value=0, max_value=max_count - 1))
    return (asset_type, mime_type, file_size, existing_count)


@st.composite
def upload_metadata_wrong_format(draw):
    """Generate metadata where the MIME type is wrong for the asset_type."""
    asset_type = draw(asset_type_strategy)
    mime_type = draw(invalid_mimes)
    # Even with valid size and count, wrong format should fail
    max_size = MAX_SIZE_BYTES[asset_type]
    file_size = draw(st.integers(min_value=1, max_value=max_size))
    max_count = MAX_COUNT[asset_type]
    existing_count = draw(st.integers(min_value=0, max_value=max_count - 1))
    return (asset_type, mime_type, file_size, existing_count)


@st.composite
def upload_metadata_too_large(draw):
    """Generate metadata where file size exceeds the limit."""
    asset_type = draw(asset_type_strategy)
    mime_type = draw(valid_mime_for_type[asset_type])
    max_size = MAX_SIZE_BYTES[asset_type]
    # Size strictly exceeds max
    file_size = draw(st.integers(min_value=max_size + 1, max_value=max_size * 2))
    max_count = MAX_COUNT[asset_type]
    existing_count = draw(st.integers(min_value=0, max_value=max_count - 1))
    return (asset_type, mime_type, file_size, existing_count)


@st.composite
def upload_metadata_count_exceeded(draw):
    """Generate metadata where existing count is at or above the max."""
    asset_type = draw(asset_type_strategy)
    mime_type = draw(valid_mime_for_type[asset_type])
    max_size = MAX_SIZE_BYTES[asset_type]
    file_size = draw(st.integers(min_value=1, max_value=max_size))
    max_count = MAX_COUNT[asset_type]
    # Existing count is already at or above the limit
    existing_count = draw(st.integers(min_value=max_count, max_value=max_count + 10))
    return (asset_type, mime_type, file_size, existing_count)


# --- Property Tests ---


@given(data=valid_upload_metadata())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_valid_upload_always_accepted(data):
    """Property 19: Valid uploads (correct format, within size, within count) are always accepted.

    **Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5, 17.11**
    """
    asset_type, mime_type, file_size, existing_count = data
    is_valid, error_code = validate_asset_upload(asset_type, mime_type, file_size, existing_count)
    assert is_valid is True, (
        f"Expected valid upload for type={asset_type}, mime={mime_type}, "
        f"size={file_size}, count={existing_count}, got error_code={error_code}"
    )
    assert error_code is None


@given(data=upload_metadata_wrong_format())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_wrong_format_always_rejected_415(data):
    """Property 19: Uploads with wrong MIME type are always rejected with 415.

    **Validates: Requirements 17.1, 17.2, 17.3, 17.5, 17.8**
    """
    asset_type, mime_type, file_size, existing_count = data
    is_valid, error_code = validate_asset_upload(asset_type, mime_type, file_size, existing_count)
    assert is_valid is False, (
        f"Expected rejection for wrong format: type={asset_type}, mime={mime_type}"
    )
    assert error_code == 415


@given(data=upload_metadata_too_large())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_oversized_file_always_rejected_413(data):
    """Property 19: Uploads exceeding size limits are always rejected with 413.

    **Validates: Requirements 17.1, 17.2, 17.3, 17.7**
    """
    asset_type, mime_type, file_size, existing_count = data
    is_valid, error_code = validate_asset_upload(asset_type, mime_type, file_size, existing_count)
    assert is_valid is False, (
        f"Expected rejection for oversized file: type={asset_type}, size={file_size}"
    )
    assert error_code == 413


@given(data=upload_metadata_count_exceeded())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_count_exceeded_always_rejected_409(data):
    """Property 19: Uploads when count limit is reached are always rejected with 409.

    **Validates: Requirements 17.4, 17.5, 17.11**
    """
    asset_type, mime_type, file_size, existing_count = data
    is_valid, error_code = validate_asset_upload(asset_type, mime_type, file_size, existing_count)
    assert is_valid is False, (
        f"Expected rejection for count exceeded: type={asset_type}, "
        f"count={existing_count}, max={MAX_COUNT[asset_type]}"
    )
    assert error_code == 409


@given(
    asset_type=asset_type_strategy,
    mime_type=st.sampled_from([
        "image/jpeg", "image/png", "video/mp4", "application/pdf",
        "text/plain", "image/gif", "application/json",
    ]),
    file_size=st.integers(min_value=1, max_value=200 * 1024 * 1024),
    existing_count=st.integers(min_value=0, max_value=40),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_accept_iff_all_conditions_met(asset_type, mime_type, file_size, existing_count):
    """Property 19: Accept iff format matches AND size within limit AND count not exceeded.

    **Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5, 17.11**
    """
    is_valid, error_code = validate_asset_upload(asset_type, mime_type, file_size, existing_count)

    format_ok = mime_type in ALLOWED_MIMES.get(asset_type, set())
    size_ok = file_size <= MAX_SIZE_BYTES.get(asset_type, 0)
    count_ok = existing_count < MAX_COUNT.get(asset_type, 0)

    expected_valid = format_ok and size_ok and count_ok

    assert is_valid == expected_valid, (
        f"Mismatch: asset_type={asset_type}, mime={mime_type}, size={file_size}, "
        f"count={existing_count} — got is_valid={is_valid}, expected={expected_valid}"
    )
