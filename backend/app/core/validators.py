"""Input validation utilities for AutoMind AI Platform."""

import re


def validate_indian_phone(phone: str) -> bool:
    """Validate an Indian mobile phone number.

    A valid Indian mobile phone number is exactly 10 digits
    and starts with 6, 7, 8, or 9.

    Args:
        phone: The phone number string to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(phone, str):
        return False
    if len(phone) != 10:
        return False
    if not phone.isdigit():
        return False
    if phone[0] not in ("6", "7", "8", "9"):
        return False
    return True


# RERA ID pattern: RERA/{2-letter state code}/{4-digit year}/{1+ digit number}
_RERA_PATTERN = re.compile(r"^RERA/[A-Z]{2}/\d{4}/\d+$")


def validate_rera_id(rera_id: str) -> bool:
    """Validate a RERA ID format.

    Valid format: RERA/{state_code}/{year}/{number}
    where state_code is 2 uppercase letters, year is 4 digits,
    and number is 1 or more digits.

    Args:
        rera_id: The RERA ID string to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(rera_id, str):
        return False
    return bool(_RERA_PATTERN.match(rera_id))
