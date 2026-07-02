"""Property-based tests for Indian phone number validation.

**Validates: Requirements 1.1, 1.8, 5.4**

Uses hypothesis to generate valid and invalid phone numbers and verify
that validate_indian_phone accepts if and only if the input is exactly
10 digits starting with 6-9.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.validators import validate_indian_phone


# --- Strategies ---

# Valid Indian phone: exactly 10 digits, first digit 6-9
valid_phone_strategy = st.from_regex(r"[6-9][0-9]{9}", fullmatch=True)

# Invalid: wrong length (too short)
too_short_strategy = st.from_regex(r"[6-9][0-9]{0,8}", fullmatch=True)

# Invalid: wrong length (too long)
too_long_strategy = st.from_regex(r"[6-9][0-9]{10,15}", fullmatch=True)

# Invalid: wrong prefix (starts with 0-5)
wrong_prefix_strategy = st.from_regex(r"[0-5][0-9]{9}", fullmatch=True)

# Invalid: non-numeric characters
non_numeric_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "P", "S", "Z")),
    min_size=1,
    max_size=20,
)

# Invalid: empty string
empty_strategy = st.just("")

# Invalid: mixed alphanumeric
mixed_strategy = st.from_regex(r"[6-9][a-z0-9]{9}", fullmatch=True).filter(
    lambda s: not s.isdigit()
)


# --- Property Tests ---


@given(phone=valid_phone_strategy)
@settings(max_examples=50)
def test_valid_phone_numbers_accepted(phone: str):
    """Property 1: Any 10-digit string starting with 6-9 is accepted."""
    assert validate_indian_phone(phone) is True


@given(phone=too_short_strategy)
@settings(max_examples=50)
def test_too_short_phone_numbers_rejected(phone: str):
    """Property 1 (inverse): Phone numbers shorter than 10 digits are rejected."""
    assume(len(phone) < 10)
    assert validate_indian_phone(phone) is False


@given(phone=too_long_strategy)
@settings(max_examples=50)
def test_too_long_phone_numbers_rejected(phone: str):
    """Property 1 (inverse): Phone numbers longer than 10 digits are rejected."""
    assert validate_indian_phone(phone) is False


@given(phone=wrong_prefix_strategy)
@settings(max_examples=50)
def test_wrong_prefix_phone_numbers_rejected(phone: str):
    """Property 1 (inverse): 10-digit numbers not starting with 6-9 are rejected."""
    assert validate_indian_phone(phone) is False


@given(phone=non_numeric_strategy)
@settings(max_examples=50)
def test_non_numeric_strings_rejected(phone: str):
    """Property 1 (inverse): Non-numeric strings are always rejected."""
    assert validate_indian_phone(phone) is False


@given(phone=empty_strategy)
def test_empty_string_rejected(phone: str):
    """Property 1 (inverse): Empty string is rejected."""
    assert validate_indian_phone(phone) is False


@given(phone=mixed_strategy)
@settings(max_examples=50)
def test_mixed_alphanumeric_rejected(phone: str):
    """Property 1 (inverse): Strings with letters mixed in are rejected."""
    assert validate_indian_phone(phone) is False


@given(phone=st.text(min_size=0, max_size=30))
@settings(max_examples=50)
def test_biconditional_property(phone: str):
    """Property 1 (biconditional): validate_indian_phone accepts iff exactly 10 digits starting with 6-9."""
    expected = (
        len(phone) == 10
        and phone.isdigit()
        and phone[0] in ("6", "7", "8", "9")
    )
    assert validate_indian_phone(phone) == expected
