"""Property-based tests for Room Revisit Event Detection.

Feature: automind-ai-platform
Tests Property 17: room_revisited event is recorded if and only if
a buyer navigates to a previously viewed room.
"""

from hypothesis import given, settings
from hypothesis import strategies as st


# --- Strategies ---

ROOM_NAMES = [
    "living_room",
    "master_bedroom",
    "bedroom_2",
    "kitchen",
    "bathroom",
    "balcony",
    "study",
    "dining_room",
    "terrace",
    "utility_room",
]


@st.composite
def st_room_view_sequence(draw):
    """Generate a random sequence of room views.

    Returns a list of room names representing a navigation sequence.
    """
    num_views = draw(st.integers(min_value=1, max_value=30))
    rooms = draw(
        st.lists(
            st.sampled_from(ROOM_NAMES),
            min_size=num_views,
            max_size=num_views,
        )
    )
    return rooms


def detect_room_revisits(room_sequence: list[str]) -> list[dict]:
    """Detect room revisit events from a sequence of room views.

    A room_revisited event should be recorded when a buyer navigates
    to a room they have previously viewed in the same session.

    Args:
        room_sequence: Ordered list of room names the buyer navigated to.

    Returns:
        List of event dicts with type and room info for each revisit.
    """
    viewed_rooms: set[str] = set()
    revisit_events: list[dict] = []

    for room in room_sequence:
        if room in viewed_rooms:
            revisit_events.append({
                "type": "room_revisited",
                "data": {"room": room},
            })
        else:
            viewed_rooms.add(room)

    return revisit_events


# --- Property 17: Room Revisit Event Detection ---


@settings(max_examples=50)
@given(room_sequence=st_room_view_sequence())
def test_property_17_room_revisit_detection(room_sequence: list[str]):
    """Property 17: Room Revisit Event Detection

    For any random sequence of room views, a room_revisited event is
    recorded if and only if the buyer navigates to a previously viewed room.

    **Validates: Requirements 6.5**
    """
    revisit_events = detect_room_revisits(room_sequence)

    # Track which rooms have been seen
    viewed: set[str] = set()
    expected_revisit_count = 0

    for room in room_sequence:
        if room in viewed:
            expected_revisit_count += 1
        else:
            viewed.add(room)

    # The number of revisit events must equal the expected count
    assert len(revisit_events) == expected_revisit_count, (
        f"Expected {expected_revisit_count} revisit events, "
        f"got {len(revisit_events)} for sequence {room_sequence}"
    )

    # Every revisit event must reference a room that was previously viewed
    seen_so_far: set[str] = set()
    revisit_idx = 0

    for room in room_sequence:
        if room in seen_so_far:
            # This is a revisit — verify the event matches
            assert revisit_idx < len(revisit_events), (
                f"Missing revisit event at index {revisit_idx}"
            )
            event = revisit_events[revisit_idx]
            assert event["type"] == "room_revisited"
            assert event["data"]["room"] == room, (
                f"Revisit event room mismatch: expected '{room}', "
                f"got '{event['data']['room']}'"
            )
            revisit_idx += 1
        else:
            seen_so_far.add(room)


@settings(max_examples=50)
@given(room_sequence=st.lists(st.sampled_from(ROOM_NAMES), min_size=1, max_size=20, unique=True))
def test_property_17_no_revisits_with_unique_rooms(room_sequence: list[str]):
    """Property 17 corollary: No revisit events when all rooms are unique.

    If a buyer never views the same room twice, no room_revisited events
    should be recorded.

    **Validates: Requirements 6.5**
    """
    revisit_events = detect_room_revisits(room_sequence)
    assert len(revisit_events) == 0, (
        f"Expected no revisit events for unique rooms, "
        f"got {len(revisit_events)} for sequence {room_sequence}"
    )


@settings(max_examples=50)
@given(
    room=st.sampled_from(ROOM_NAMES),
    repeat_count=st.integers(min_value=2, max_value=10),
)
def test_property_17_repeated_same_room(room: str, repeat_count: int):
    """Property 17 corollary: Repeated views of same room produce revisit events.

    If a buyer views the same room N times, there should be N-1 revisit events.

    **Validates: Requirements 6.5**
    """
    room_sequence = [room] * repeat_count
    revisit_events = detect_room_revisits(room_sequence)

    assert len(revisit_events) == repeat_count - 1, (
        f"Expected {repeat_count - 1} revisit events for "
        f"{repeat_count} views of '{room}', got {len(revisit_events)}"
    )

    # All events should reference the same room
    for event in revisit_events:
        assert event["data"]["room"] == room
