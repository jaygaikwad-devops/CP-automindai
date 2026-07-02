"""Unit and integration tests for the Lead Scoring Engine.

Tests calculate_score, classify_lead, classify_question, and
the alert threshold logic.
"""

import pytest
from app.services.lead_engine import (
    SIGNAL_WEIGHTS,
    calculate_score,
    classify_lead,
    classify_question,
)


class TestCalculateScore:
    """Unit tests for calculate_score function."""

    def test_empty_signals_returns_zero(self):
        score, classification, breakdown = calculate_score([])
        assert score == 0
        assert classification == "browsing"
        assert breakdown == []

    def test_single_signal(self):
        signals = [{"type": "price_question_asked"}]
        score, classification, breakdown = calculate_score(signals)
        assert score == 2
        assert classification == "browsing"
        assert len(breakdown) == 1
        assert breakdown[0] == {"type": "price_question_asked", "points": 2}

    def test_emi_question_highest_weight(self):
        signals = [{"type": "emi_question_asked"}]
        score, _, _ = calculate_score(signals)
        assert score == 3

    def test_duplicate_signals_counted_once(self):
        signals = [
            {"type": "price_question_asked"},
            {"type": "price_question_asked"},
            {"type": "price_question_asked"},
        ]
        score, _, _ = calculate_score(signals)
        assert score == 2  # Only counted once

    def test_room_revisited_max_two(self):
        signals = [
            {"type": "room_revisited"},
            {"type": "room_revisited"},
            {"type": "room_revisited"},
            {"type": "room_revisited"},
        ]
        score, _, _ = calculate_score(signals)
        assert score == 2  # Max 2 distinct rooms

    def test_score_capped_at_10(self):
        # Use all signals to exceed 10
        signals = [
            {"type": "time_on_tour_3min_plus"},  # +2
            {"type": "room_revisited"},  # +1
            {"type": "room_revisited"},  # +1
            {"type": "price_question_asked"},  # +2
            {"type": "emi_question_asked"},  # +3
            {"type": "rera_question_asked"},  # +1
            {"type": "amenities_question_asked"},  # +1
            {"type": "returned_within_24h"},  # +2
            {"type": "whatsapp_share_clicked"},  # +1
            {"type": "visit_booking_clicked"},  # +4
        ]
        # Total would be 18, capped at 10
        score, _, _ = calculate_score(signals)
        assert score == 10

    def test_visit_booking_triggers_visit_booked_classification(self):
        signals = [{"type": "visit_booking_clicked"}]
        score, classification, _ = calculate_score(signals)
        assert score == 4
        assert classification == "visit_booked"

    def test_hot_classification_at_score_7(self):
        signals = [
            {"type": "emi_question_asked"},  # +3
            {"type": "price_question_asked"},  # +2
            {"type": "returned_within_24h"},  # +2
        ]
        score, classification, _ = calculate_score(signals)
        assert score == 7
        assert classification == "hot"

    def test_warm_classification_at_score_4(self):
        signals = [
            {"type": "time_on_tour_3min_plus"},  # +2
            {"type": "price_question_asked"},  # +2
        ]
        score, classification, _ = calculate_score(signals)
        assert score == 4
        assert classification == "warm"

    def test_unknown_signal_type_ignored(self):
        signals = [
            {"type": "unknown_signal"},
            {"type": "price_question_asked"},
        ]
        score, _, _ = calculate_score(signals)
        assert score == 2  # Only price counted


class TestClassifyLead:
    """Unit tests for classify_lead function."""

    def test_browsing_for_low_scores(self):
        for score in range(0, 4):
            assert classify_lead(score, False) == "browsing"

    def test_warm_for_mid_scores(self):
        for score in range(4, 7):
            assert classify_lead(score, False) == "warm"

    def test_hot_for_high_scores(self):
        for score in range(7, 10):
            assert classify_lead(score, False) == "hot"

    def test_visit_booked_overrides_any_score(self):
        for score in range(0, 11):
            assert classify_lead(score, True) == "visit_booked"


class TestClassifyQuestion:
    """Unit tests for classify_question function."""

    def test_price_keywords(self):
        for msg in ["What is the price?", "Tell me the cost", "What rate per sqft?"]:
            signal, weight = classify_question(msg)
            assert signal == "price_question_asked"
            assert weight == 2

    def test_emi_keywords(self):
        for msg in ["What is the EMI?", "Can I get a loan?", "Mortgage options?", "Monthly installment?"]:
            signal, weight = classify_question(msg)
            assert signal == "emi_question_asked"
            assert weight == 3

    def test_rera_keywords(self):
        for msg in ["Is this RERA registered?", "Show registration details"]:
            signal, weight = classify_question(msg)
            assert signal == "rera_question_asked"
            assert weight == 1

    def test_amenities_keywords(self):
        for msg in ["What amenities are available?", "Is there a gym?", "Does it have a pool?",
                    "Tell me about the garden", "Parking available?", "Is there a clubhouse?"]:
            signal, weight = classify_question(msg)
            assert signal == "amenities_question_asked"
            assert weight == 1

    def test_general_question_no_signal(self):
        signal, weight = classify_question("Hello, how are you?")
        assert signal is None
        assert weight == 0

    def test_case_insensitive(self):
        signal, weight = classify_question("WHAT IS THE PRICE?")
        assert signal == "price_question_asked"

    def test_keyword_as_substring(self):
        signal, weight = classify_question("What is the price-range here?")
        assert signal == "price_question_asked"
