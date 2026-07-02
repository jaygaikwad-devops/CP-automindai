"""Property-based tests for RERA ID validation.

**Validates: Requirements 1.5**

Uses hypothesis to generate valid and invalid RERA IDs and verify
that validate_rera_id accepts if and only if the input matches
the pattern RERA/{2-letter-state}/{4-digit-year}/{1+digit-number}.
"""

import re

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.validators import validate_rera_id


# --- Strategies ---

# Valid state codes: 2 uppercase letters
state_code_strategy = st.from_regex(r"[A-Z]{2}", fullmatch=True)

# Valid year: 4 digits
year_strategy = st.from_regex(r"[0-9]{4}", fullmatch=True)

# Valid number: 1+ digits
number_strategy = st.from_regex(r"[0-9]{1,10}", fullmatch=True)

# Valid RERA ID strategy
valid_rera_strategy = st.builds(
    lambda state, year, number: f"RERA/{state}/{year}/{number}",
    state=state_code_strategy,
    year=year_strategy,
    number=number_strategy,
)

# Invalid: missing RERA prefix
missing_prefix_strategy = st.builds(
    lambda state, year, number: f"{state}/{year}/{number}",
    state=state_code_strategy,
    year=year_strategy,
    number=number_strategy,
)

# Invalid: lowercase state code
lowercase_state_strategy = st.builds(
    lambda state, year, number: f"RERA/{state.lower()}/{year}/{number}",
    state=state_code_strategy,
    year=year_strategy,
    number=number_strategy,
)

# Invalid: wrong state code length (1 letter or 3+ letters)
wrong_state_len_strategy = st.one_of(
    st.builds(
        lambda state, year, number: f"RERA/{state}/{year}/{number}",
        state=st.from_regex(r"[A-Z]{1}", fullmatch=True),
        year=year_strategy,
        number=number_strategy,
    ),
    st.builds(
        lambda state, year, number: f"RERA/{state}/{year}/{number}",
        state=st.from_regex(r"[A-Z]{3,5}", fullmatch=True),
        year=year_strategy,
        number=number_strategy,
    ),
)

# Invalid: wrong year (not 4 digits)
wrong_year_strategy = st.one_of(
    st.builds(
        lambda state, year, number: f"RERA/{state}/{year}/{number}",
        state=state_code_strategy,
        year=st.from_regex(r"[0-9]{1,3}", fullmatch=True),
        number=number_strategy,
    ),
    st.builds(
        lambda state, year, number: f"RERA/{state}/{year}/{number}",
        state=state_code_strategy,
        year=st.from_regex(r"[0-9]{5,7}", fullmatch=True),
        number=number_strategy,
    ),
)

# Invalid: empty number
empty_number_strategy = st.builds(
    lambda state, year: f"RERA/{state}/{year}/",
    state=state_code_strategy,
    year=year_strategy,
)

# Invalid: non-numeric number
non_numeric_number_strategy = st.builds(
    lambda state, year, number: f"RERA/{state}/{year}/{number}",
    state=state_code_strategy,
    year=year_strategy,
    number=st.from_regex(r"[a-z]{1,5}", fullmatch=True),
)


# --- Property Tests ---


@given(rera_id=valid_rera_strategy)
@settings(max_examples=50)
def test_valid_rera_ids_accepted(rera_id: str):
    """Property 2: Any string matching RERA/{2-letter-state}/{4-digit-year}/{1+digit-number} is accepted."""
    assert validate_rera_id(rera_id) is True


@given(rera_id=missing_prefix_strategy)
@settings(max_examples=50)
def test_missing_prefix_rejected(rera_id: str):
    """Property 2 (inverse): IDs without RERA/ prefix are rejected."""
    assert validate_rera_id(rera_id) is False


@given(rera_id=lowercase_state_strategy)
@settings(max_examples=50)
def test_lowercase_state_rejected(rera_id: str):
    """Property 2 (inverse): Lowercase state codes are rejected."""
    assert validate_rera_id(rera_id) is False


@given(rera_id=wrong_state_len_strategy)
@settings(max_examples=50)
def test_wrong_state_length_rejected(rera_id: str):
    """Property 2 (inverse): State codes not exactly 2 letters are rejected."""
    assert validate_rera_id(rera_id) is False


@given(rera_id=wrong_year_strategy)
@settings(max_examples=50)
def test_wrong_year_length_rejected(rera_id: str):
    """Property 2 (inverse): Years not exactly 4 digits are rejected."""
    assert validate_rera_id(rera_id) is False


@given(rera_id=empty_number_strategy)
@settings(max_examples=50)
def test_empty_number_rejected(rera_id: str):
    """Property 2 (inverse): Empty number part is rejected."""
    assert validate_rera_id(rera_id) is False


@given(rera_id=non_numeric_number_strategy)
@settings(max_examples=50)
def test_non_numeric_number_rejected(rera_id: str):
    """Property 2 (inverse): Non-numeric number parts are rejected."""
    assert validate_rera_id(rera_id) is False


@given(text=st.text(min_size=0, max_size=50))
@settings(max_examples=50)
def test_biconditional_property(text: str):
    """Property 2 (biconditional): validate_rera_id accepts iff pattern matches RERA/{2-letter}/{4-digit}/{1+digit}."""
    pattern = re.compile(r"^RERA/[A-Z]{2}/\d{4}/\d+$")
    expected = bool(pattern.match(text))
    assert validate_rera_id(text) == expected
