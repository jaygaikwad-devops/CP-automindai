"""Property-based tests for duplicate partnership rejection.

**Validates: Requirements 16.7**

Uses hypothesis to generate random assignment sequences with duplicates
and verify that duplicate CP-project pairs always return 409 Conflict.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import create_access_token
from app.services.redis_cache import get_redis


# --- Strategies ---

# Generate a list of CP-project assignments where at least one is duplicated
@st.composite
def assignment_sequences_with_duplicates(draw):
    """Generate a sequence of assignments that includes at least one duplicate."""
    # Generate 2-5 unique CP IDs and 2-5 unique project IDs
    num_cps = draw(st.integers(min_value=2, max_value=5))
    num_projects = draw(st.integers(min_value=2, max_value=5))

    cp_ids = [str(uuid.uuid4()) for _ in range(num_cps)]
    project_ids = [str(uuid.uuid4()) for _ in range(num_projects)]

    # Generate a sequence of assignments
    assignments = draw(
        st.lists(
            st.tuples(
                st.sampled_from(cp_ids),
                st.sampled_from(project_ids),
            ),
            min_size=3,
            max_size=10,
        )
    )

    # Ensure at least one duplicate exists
    if len(assignments) >= 2:
        # Force a duplicate by repeating the first assignment
        duplicate_pair = assignments[0]
        # Insert duplicate at a random position after the first
        insert_pos = draw(st.integers(min_value=1, max_value=len(assignments)))
        assignments.insert(insert_pos, duplicate_pair)

    return assignments


# --- Helpers ---


def _create_admin_token() -> str:
    """Create a JWT token with admin role."""
    return create_access_token(
        data={"sub": "admin-sub", "phone": "9999999999", "role": "admin"}
    )


async def _get_client():
    """Create a test client with mocked dependencies."""
    from app.main import app

    mock_redis = AsyncMock()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.rollback = AsyncMock()

    async def override_get_redis():
        return mock_redis

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client, app, mock_db


# --- Property Tests ---


@pytest.mark.asyncio
@given(assignments=assignment_sequences_with_duplicates())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_duplicate_partnership_always_returns_409(assignments: list):
    """Property 24: Duplicate CP-project pair always returns conflict error.

    Simulates a sequence of partnership assignments and verifies
    that the second attempt to create the same CP-project pair returns 409.
    """
    client, app, mock_db = await _get_client()
    try:
        token = _create_admin_token()
        seen_pairs = set()

        for cp_id, project_id in assignments:
            pair = (cp_id, project_id)
            is_duplicate = pair in seen_pairs

            # Mock project and CP lookup to always succeed
            mock_project = MagicMock()
            mock_project.builder_id = uuid.uuid4()
            mock_cp = MagicMock()

            call_count = [0]

            async def mock_execute(stmt, _project=mock_project, _cp=mock_cp):
                call_count[0] += 1
                result = MagicMock()
                if call_count[0] == 1:
                    result.scalar_one_or_none = MagicMock(return_value=_project)
                else:
                    result.scalar_one_or_none = MagicMock(return_value=_cp)
                return result

            mock_db.execute = mock_execute

            if is_duplicate:
                # Simulate IntegrityError on duplicate
                mock_db.flush = AsyncMock(
                    side_effect=IntegrityError("duplicate", {}, Exception())
                )
            else:
                mock_db.flush = AsyncMock()

            response = await client.post(
                "/api/v1/admin/partnerships",
                json={"cp_id": cp_id, "project_id": project_id},
                headers={"Authorization": f"Bearer {token}"},
            )

            if is_duplicate:
                assert response.status_code == 409, (
                    f"Expected 409 for duplicate pair ({cp_id}, {project_id}), "
                    f"got {response.status_code}"
                )
            else:
                assert response.status_code == 201, (
                    f"Expected 201 for new pair ({cp_id}, {project_id}), "
                    f"got {response.status_code}"
                )

            seen_pairs.add(pair)
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
