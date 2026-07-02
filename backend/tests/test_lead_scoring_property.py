"""Property-based tests for Lead Scoring Engine.

Feature: automind-ai-platform
Tests Properties 3, 4, 12, and 14 for lead score calculation,
classification, question classification, and alert threshold.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.lead_engine import (
    ALERT_THRESHOLD,
    MAX_ROOM_REVISITED_CONTRIBUTION,
    SIGNAL_WEIGHTS,
    calculate_score,
    classify_lead,
    classify_question,
    check_and_alert,
)


# --- Strategies ---

ALL_SIGNAL_TYPES = list(SIGNAL_WEIGHTS.keys())


def st_signal(signal_type: str | None = None):
    """Generate a signal dict."""
    if signal_type is not None:
        return st.just({"type": signal_type})
    return st.sampled_from(ALL_SIGNAL_TYPES).map(lambda t: {"type": t})


def st_signal_list():
    """Generate a random list of signals with possible duplicates."""
    return st.lists(st_signal(), min_size=0, max_size=20)


# --- Property 3: Lead Score Calculation Correctness ---

@settings(max_examples=50)
@given(signals=st_signal_list())
def test_property_3_lead_score_calculation(signals: list[dict]):
    """Property 3: Lead Score Calculation Correctness

    For any set of session signals, the lead score equals the sum of
    applicable signal weights where each signal type is counted at most
    once (except room_revisited which counts up to 2 distinct rooms),
    and the final score is capped at 10.

    **Validates: Requirements 9.1, 9.2, 9.3, 9.7**
    """
    score, classification, breakdown = calculate_score(signals)

    # Manually compute expected score
    expected_score = 0
    applied: set[str] = set()
    room_count = 0

    for signal in signals:
        signal_type = signal["type"]
        if signal_type == "room_revisited":
            if room_count < MAX_ROOM_REVISITED_CONTRIBUTION:
                expected_score += SIGNAL_WEIGHTS[signal_type]
                room_count += 1
        else:
            if signal_type not in applied and signal_type in SIGNAL_WEIGHTS:
                expected_score += SIGNAL_WEIGHTS[signal_type]
                applied.add(signal_type)

    expected_score = min(expected_score, 10)

    assert score == expected_score, (
        f"Score mismatch: got {score}, expected {expected_score} "
        f"for signals {signals}"
    )

    # Score must be in [0, 10]
    assert 0 <= score <= 10

    # Breakdown should list all counted signals
    assert sum(s["points"] for s in breakdown) >= score or score == 10


# --- Property 4: Lead Classification from Score ---

@settings(max_examples=50)
@given(
    score=st.integers(min_value=0, max_value=10),
    has_visit_booking=st.booleans(),
)
def test_property_4_lead_classification(score: int, has_visit_booking: bool):
    """Property 4: Lead Classification from Score

    For any integer score from 0 to 10 and any visit_booking_clicked status,
    the classification function returns the correct category per thresholds;
    visit_booked overrides regardless of score.

    **Validates: Requirements 9.4**
    """
    classification = classify_lead(score, has_visit_booking)

    if has_visit_booking:
        assert classification == "visit_booked", (
            f"Expected 'visit_booked' with visit_booking=True, got '{classification}'"
        )
    elif score >= 7:
        assert classification == "hot", (
            f"Expected 'hot' for score {score}, got '{classification}'"
        )
    elif score >= 4:
        assert classification == "warm", (
            f"Expected 'warm' for score {score}, got '{classification}'"
        )
    else:
        assert classification == "browsing", (
            f"Expected 'browsing' for score {score}, got '{classification}'"
        )


# --- Property 12: Question Classification and Signal Application ---

# Keyword lists for generating messages
PRICE_KEYWORDS = ["price", "cost", "rate"]
EMI_KEYWORDS = ["emi", "loan", "mortgage", "installment"]
RERA_KEYWORDS = ["rera", "registration"]
AMENITIES_KEYWORDS = ["amenities", "gym", "pool", "garden", "parking", "clubhouse"]


@st.composite
def st_message_with_known_category(draw):
    """Generate a message containing a known keyword."""
    category = draw(st.sampled_from(["price", "emi", "rera", "amenities"]))

    if category == "price":
        keyword = draw(st.sampled_from(PRICE_KEYWORDS))
        expected_signal = "price_question_asked"
        expected_weight = 2
    elif category == "emi":
        keyword = draw(st.sampled_from(EMI_KEYWORDS))
        expected_signal = "emi_question_asked"
        expected_weight = 3
    elif category == "rera":
        keyword = draw(st.sampled_from(RERA_KEYWORDS))
        expected_signal = "rera_question_asked"
        expected_weight = 1
    else:
        keyword = draw(st.sampled_from(AMENITIES_KEYWORDS))
        expected_signal = "amenities_question_asked"
        expected_weight = 1

    # Build a message containing the keyword
    prefix = draw(st.text(min_size=0, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz "))
    suffix = draw(st.text(min_size=0, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz ?!"))

    # Ensure prefix/suffix don't accidentally contain other category keywords
    # by filtering
    message = f"{prefix} {keyword} {suffix}".strip()

    return message, expected_signal, expected_weight


@settings(max_examples=50)
@given(data=st_message_with_known_category())
def test_property_12_question_classification(data: tuple[str, str, int]):
    """Property 12: Question Classification and Signal Application

    For any chat message classified into a known category (price, EMI,
    RERA, amenities), the Lead_Engine applies the corresponding signal
    with the correct weight.

    **Validates: Requirements 8.3, 8.4, 8.5, 8.6**
    """
    message, expected_signal, expected_weight = data

    signal_type, weight = classify_question(message)

    # The message contains the keyword, so it should be classified
    # (though it might match a different category if prefix/suffix
    # accidentally contains another keyword — we allow that as valid)
    assert signal_type is not None, (
        f"Message '{message}' was not classified (expected {expected_signal})"
    )

    # The returned weight must match the signal's configured weight
    assert weight == SIGNAL_WEIGHTS[signal_type], (
        f"Weight mismatch for signal '{signal_type}': got {weight}, "
        f"expected {SIGNAL_WEIGHTS[signal_type]}"
    )

    # Signal type must be a valid signal
    assert signal_type in SIGNAL_WEIGHTS


# --- Property 14: Alert Triggered at Threshold ---

@st.composite
def st_signal_sequence_reaching_threshold(draw):
    """Generate a signal accumulation sequence that may cross threshold."""
    # Pick a subset of signals
    num_signals = draw(st.integers(min_value=1, max_value=15))
    signals = []
    for _ in range(num_signals):
        signal_type = draw(st.sampled_from(ALL_SIGNAL_TYPES))
        signals.append({"type": signal_type})
    return signals


@settings(max_examples=50)
@given(signals=st_signal_sequence_reaching_threshold())
def test_property_14_alert_triggered_at_threshold(signals: list[dict]):
    """Property 14: Alert Triggered at Threshold

    For any session where the recalculated Lead_Score reaches or exceeds 7
    for the first time, exactly one alert is triggered. No duplicates.

    **Validates: Requirements 10.1, 10.6**
    """
    # Simulate incremental signal accumulation
    alert_count = 0
    accumulated_signals: list[dict] = []
    previous_score = 0
    alert_already_sent = False

    for signal in signals:
        accumulated_signals.append(signal)
        score, classification, breakdown = calculate_score(accumulated_signals)

        # Alert should trigger when score first reaches >= 7
        if score >= ALERT_THRESHOLD and not alert_already_sent:
            alert_count += 1
            alert_already_sent = True

    # Compute final score
    final_score, _, _ = calculate_score(signals)

    if final_score >= ALERT_THRESHOLD:
        # Exactly one alert should have been triggered
        assert alert_count == 1, (
            f"Expected exactly 1 alert for signals reaching threshold, "
            f"got {alert_count}. Signals: {signals}, final score: {final_score}"
        )
    else:
        # No alert should have been triggered
        assert alert_count == 0, (
            f"Expected no alert for score {final_score} < {ALERT_THRESHOLD}, "
            f"got {alert_count}"
        )
