"""Property-based tests for upload blocked by project status.

**Validates: Requirements 17.12**

Uses hypothesis to generate random project statuses and verify that
uploads are rejected (409) if and only if status is
"processing_in_progress" or "tour_ready".
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.services.asset_validation import BLOCKED_STATUSES, is_upload_blocked_by_status


# --- Strategies ---

# All known project statuses
all_statuses = st.sampled_from([
    "not_started",
    "processing_in_progress",
    "processing_failed",
    "processing_timeout",
    "tour_ready",
])

# Statuses that should block uploads
blocking_statuses = st.sampled_from(["processing_in_progress", "tour_ready"])

# Statuses that should allow uploads
non_blocking_statuses = st.sampled_from([
    "not_started",
    "processing_failed",
    "processing_timeout",
])


# --- Property Tests ---


@given(status=blocking_statuses)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_blocking_status_always_blocks_upload(status):
    """Property 21: Upload is always blocked when status is processing_in_progress or tour_ready.

    **Validates: Requirements 17.12**
    """
    assert is_upload_blocked_by_status(status) is True, (
        f"Expected upload to be blocked for status '{status}'"
    )


@given(status=non_blocking_statuses)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_non_blocking_status_always_allows_upload(status):
    """Property 21: Upload is always allowed when status is not processing_in_progress or tour_ready.

    **Validates: Requirements 17.12**
    """
    assert is_upload_blocked_by_status(status) is False, (
        f"Expected upload to be allowed for status '{status}'"
    )


@given(status=all_statuses)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_upload_blocked_iff_status_in_blocked_set(status):
    """Property 21: Upload rejected (409) iff status is processing_in_progress or tour_ready.

    **Validates: Requirements 17.12**
    """
    result = is_upload_blocked_by_status(status)
    expected = status in BLOCKED_STATUSES

    assert result == expected, (
        f"Status '{status}': got blocked={result}, expected blocked={expected}"
    )
