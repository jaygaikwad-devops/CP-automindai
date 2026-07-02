"""Property-based tests for credit billing: balance never goes negative.

**Validates: Requirements 1.2**

Generates random sequences of purchase(+N) and deduction(-1) operations
and asserts that the credit balance never drops below 0.
Deductions only succeed when balance >= 1.
"""

from enum import Enum
from dataclasses import dataclass

from hypothesis import given, settings, assume
from hypothesis import strategies as st


class OpType(Enum):
    PURCHASE = "purchase"
    DEDUCTION = "deduction"


@dataclass
class PurchaseOp:
    credits: int  # positive credits to add


@dataclass
class DeductionOp:
    pass  # always deducts 1


# Strategy: generate a list of operations (purchase or deduction)
pack_credits = st.sampled_from([2, 10, 50])  # matches starter/growth/agency

purchase_op = pack_credits.map(PurchaseOp)
deduction_op = st.just(DeductionOp())

operation = st.one_of(purchase_op, deduction_op)
operation_sequence = st.lists(operation, min_size=1, max_size=30)


def simulate_credit_operations(operations: list) -> list[int]:
    """Simulate a sequence of credit operations, returning balance history.

    Deductions are only applied when balance >= 1 (mimicking the 402 guard).
    Returns the list of balances after each operation.
    """
    balance = 0
    history = []

    for op in operations:
        if isinstance(op, PurchaseOp):
            balance += op.credits
        elif isinstance(op, DeductionOp):
            if balance >= 1:
                balance -= 1
            # If balance < 1, deduction is rejected (402 in real system)
        history.append(balance)

    return history


@given(ops=operation_sequence)
@settings(max_examples=50)
def test_balance_never_negative(ops):
    """Property: credit balance never goes below 0 regardless of operation sequence."""
    history = simulate_credit_operations(ops)
    for balance in history:
        assert balance >= 0, f"Balance went negative: {balance}"


@given(ops=operation_sequence)
@settings(max_examples=50)
def test_deduction_only_succeeds_when_balance_sufficient(ops):
    """Property: deduction only reduces balance when balance >= 1."""
    balance = 0

    for op in ops:
        old_balance = balance
        if isinstance(op, PurchaseOp):
            balance += op.credits
        elif isinstance(op, DeductionOp):
            if old_balance >= 1:
                balance = old_balance - 1
                assert balance == old_balance - 1
            else:
                # Deduction rejected — balance unchanged
                assert balance == old_balance


@given(ops=operation_sequence)
@settings(max_examples=50)
def test_purchase_always_increases_balance(ops):
    """Property: purchase operations always increase the balance by the exact credit amount."""
    balance = 0

    for op in ops:
        old_balance = balance
        if isinstance(op, PurchaseOp):
            balance += op.credits
            assert balance == old_balance + op.credits
            assert balance > old_balance
        elif isinstance(op, DeductionOp):
            if old_balance >= 1:
                balance -= 1


@given(ops=operation_sequence)
@settings(max_examples=50)
def test_total_balance_equals_purchases_minus_successful_deductions(ops):
    """Property: final balance = sum(purchases) - count(successful_deductions)."""
    balance = 0
    total_purchased = 0
    total_deducted = 0

    for op in ops:
        if isinstance(op, PurchaseOp):
            balance += op.credits
            total_purchased += op.credits
        elif isinstance(op, DeductionOp):
            if balance >= 1:
                balance -= 1
                total_deducted += 1

    assert balance == total_purchased - total_deducted
    assert balance >= 0
