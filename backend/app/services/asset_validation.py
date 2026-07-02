"""Pure validation functions for asset upload.

These are extracted as pure functions to enable property-based testing
without needing HTTP or database dependencies.
"""

# Allowed MIME types per asset_type
ALLOWED_MIMES: dict[str, set[str]] = {
    "image": {"image/jpeg", "image/png"},
    "video": {"video/mp4"},
    "brochure": {"application/pdf"},
    "floor_plan": {"image/jpeg", "image/png", "application/pdf"},
}

# Maximum file size in bytes per asset_type
MAX_SIZE_BYTES: dict[str, int] = {
    "image": 20 * 1024 * 1024,       # 20 MB
    "video": 100 * 1024 * 1024,      # 100 MB
    "brochure": 20 * 1024 * 1024,    # 20 MB
    "floor_plan": 20 * 1024 * 1024,  # 20 MB
}

# Maximum count per project per asset_type
MAX_COUNT: dict[str, int] = {
    "image": 30,
    "video": 3,
    "brochure": 5,
    "floor_plan": 1,
}

# Statuses that block uploads
BLOCKED_STATUSES: set[str] = {"processing_in_progress", "tour_ready"}


def validate_asset_upload(
    asset_type: str, mime_type: str, file_size: int, existing_count: int
) -> tuple[bool, int | None]:
    """Validate whether an asset upload should be accepted.

    Args:
        asset_type: The type of asset being uploaded.
        mime_type: The MIME type of the uploaded file.
        file_size: The size of the file in bytes.
        existing_count: Current count of this asset_type for the project.

    Returns:
        Tuple of (is_valid, error_status_code).
        If is_valid is True, error_status_code is None.
        If is_valid is False, error_status_code is 413, 415, or 409.
    """
    # Check format
    allowed = ALLOWED_MIMES.get(asset_type)
    if allowed is None or mime_type not in allowed:
        return (False, 415)

    # Check size
    max_size = MAX_SIZE_BYTES.get(asset_type)
    if max_size is not None and file_size > max_size:
        return (False, 413)

    # Check count
    max_count = MAX_COUNT.get(asset_type)
    if max_count is not None and existing_count >= max_count:
        return (False, 409)

    return (True, None)


def is_upload_blocked_by_status(tour_status: str) -> bool:
    """Check whether a project's tour_status blocks uploads.

    Args:
        tour_status: The current tour_status of the project.

    Returns:
        True if uploads should be blocked, False otherwise.
    """
    return tour_status in BLOCKED_STATUSES


def is_processing_eligible(image_count: int, floor_plan_count: int) -> tuple[bool, str | None]:
    """Check whether a project is eligible to trigger processing.

    Args:
        image_count: Number of image assets for the project.
        floor_plan_count: Number of floor_plan assets for the project.

    Returns:
        Tuple of (is_eligible, error_reason).
        If eligible, error_reason is None.
        If not eligible, error_reason is "insufficient_images" or "missing_floor_plan".
    """
    if floor_plan_count != 1:
        return (False, "missing_floor_plan")
    if image_count < 10:
        return (False, "insufficient_images")
    return (True, None)
