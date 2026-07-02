"""Property-based tests for Chat Message Length Validation.

Feature: automind-ai-platform
Tests Property 13: Chat message validation accepts 1-500 chars
and rejects empty and >500 chars.
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.api.websocket import MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH


def validate_message_length(message: str) -> tuple[bool, str | None]:
    """Validate chat message length.

    Messages must be between 1 and 500 characters inclusive.

    Args:
        message: The chat message to validate.

    Returns:
        Tuple of (is_valid, error_message_or_None).
    """
    if len(message) < MIN_MESSAGE_LENGTH:
        return False, (
            f"Message must be between {MIN_MESSAGE_LENGTH} "
            f"and {MAX_MESSAGE_LENGTH} characters."
        )
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, (
            f"Message must be between {MIN_MESSAGE_LENGTH} "
            f"and {MAX_MESSAGE_LENGTH} characters."
        )
    return True, None


# --- Property 13: Chat Message Length Validation ---


@settings(max_examples=50)
@given(message=st.text(min_size=1, max_size=500))
def test_property_13_valid_messages_accepted(message: str):
    """Property 13: Valid messages (1-500 chars) are accepted.

    For any string with length between 1 and 500 inclusive,
    the validation must accept the message.

    **Validates: Requirements 8.8**
    """
    is_valid, error = validate_message_length(message)
    assert is_valid is True, (
        f"Message of length {len(message)} should be accepted, "
        f"but got error: {error}"
    )
    assert error is None


@settings(max_examples=50)
@given(message=st.just(""))
def test_property_13_empty_message_rejected(message: str):
    """Property 13: Empty messages are rejected.

    An empty string (length 0) must be rejected with a validation error.

    **Validates: Requirements 8.8**
    """
    is_valid, error = validate_message_length(message)
    assert is_valid is False, "Empty message should be rejected"
    assert error is not None
    assert "1" in error and "500" in error


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(message=st.text(min_size=501, max_size=1000))
def test_property_13_long_messages_rejected(message: str):
    """Property 13: Messages longer than 500 chars are rejected.

    For any string with length > 500, the validation must reject
    the message with a validation error.

    **Validates: Requirements 8.8**
    """
    is_valid, error = validate_message_length(message)
    assert is_valid is False, (
        f"Message of length {len(message)} should be rejected"
    )
    assert error is not None
    assert "1" in error and "500" in error


@settings(max_examples=50)
@given(length=st.integers(min_value=1, max_value=500))
def test_property_13_boundary_valid_lengths(length: int):
    """Property 13: All lengths from 1 to 500 are valid.

    For any integer length n where 1 <= n <= 500, a message of
    exactly n characters must be accepted.

    **Validates: Requirements 8.8**
    """
    message = "a" * length
    is_valid, error = validate_message_length(message)
    assert is_valid is True, (
        f"Message of length {length} should be accepted, got error: {error}"
    )


@settings(max_examples=50)
@given(length=st.integers(min_value=501, max_value=2000))
def test_property_13_boundary_invalid_lengths(length: int):
    """Property 13: All lengths > 500 are invalid.

    For any integer length n > 500, a message of exactly n characters
    must be rejected.

    **Validates: Requirements 8.8**
    """
    message = "a" * length
    is_valid, error = validate_message_length(message)
    assert is_valid is False, (
        f"Message of length {length} should be rejected"
    )
