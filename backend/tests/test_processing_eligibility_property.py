"""Property-based tests for processing eligibility.

**Validates: Requirements 17.9, 17.6**

Uses hypothesis to generate random asset states and verify that
the processing trigger is enabled if and only if image_count >= 10
AND floor_plan_count == 1.
"""

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.services.asset_validation import is_processing_eligible


# --- Strategies ---

image_count_strategy = st.integers(min_value=0, max_value=35)
floor_plan_count_strategy = st.integers(min_value=0, max_value=3)


# --- Property Tests ---


@given(
    image_count=image_count_strategy,
    floor_plan_count=floor_plan_count_strategy,
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_processing_eligible_iff_images_gte_10_and_floor_plan_eq_1(
    image_count, floor_plan_count
):
    """Property 20: Trigger enabled iff image_count >= 10 AND floor_plan_count == 1.

    **Validates: Requirements 17.9, 17.6**
    """
    eligible, error_reason = is_processing_eligible(image_count, floor_plan_count)

    expected_eligible = (image_count >= 10) and (floor_plan_count == 1)

    assert eligible == expected_eligible, (
        f"Mismatch: images={image_count}, floor_plans={floor_plan_count} — "
        f"got eligible={eligible}, expected={expected_eligible}"
    )

    if not eligible:
        # Error reason should be specific
        if floor_plan_count != 1:
            assert error_reason == "missing_floor_plan", (
                f"Expected 'missing_floor_plan' for floor_plan_count={floor_plan_count}, "
                f"got '{error_reason}'"
            )
        else:
            assert error_reason == "insufficient_images", (
                f"Expected 'insufficient_images' for image_count={image_count}, "
                f"got '{error_reason}'"
            )
    else:
        assert error_reason is None


@given(
    image_count=st.integers(min_value=10, max_value=30),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_eligible_with_enough_images_and_one_floor_plan(image_count):
    """Property 20: Always eligible when images >= 10 and floor_plan == 1.

    **Validates: Requirements 17.9, 17.6**
    """
    eligible, error_reason = is_processing_eligible(image_count, floor_plan_count=1)
    assert eligible is True
    assert error_reason is None


@given(
    image_count=st.integers(min_value=0, max_value=9),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_not_eligible_with_insufficient_images(image_count):
    """Property 20: Never eligible when images < 10 (even with floor plan).

    **Validates: Requirements 17.9**
    """
    eligible, error_reason = is_processing_eligible(image_count, floor_plan_count=1)
    assert eligible is False
    assert error_reason == "insufficient_images"


@given(
    image_count=st.integers(min_value=10, max_value=30),
    floor_plan_count=st.integers(min_value=0, max_value=3).filter(lambda x: x != 1),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_not_eligible_without_exactly_one_floor_plan(image_count, floor_plan_count):
    """Property 20: Never eligible when floor_plan_count != 1.

    **Validates: Requirements 17.6**
    """
    eligible, error_reason = is_processing_eligible(image_count, floor_plan_count)
    assert eligible is False
    assert error_reason == "missing_floor_plan"
