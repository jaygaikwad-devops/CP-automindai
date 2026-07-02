"""Property-based tests for multi-tenant data isolation.

**Validates: Requirements 3.1, 12.1, 12.2, 12.4**

Uses hypothesis to generate random CP/project/partnership combinations
and verify that access is denied (403) for unassigned projects and
granted for assigned ones.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.core.tenant_isolation import require_project_access


# --- Strategies ---

@st.composite
def tenant_isolation_scenario(draw):
    """Generate a random CP/project/partnership scenario.

    Returns a dict with:
    - cp_id: the CP making the request
    - project_id: the project being accessed
    - has_partnership: whether the CP has a valid partnership for this project
    - role: the user role (cp or admin)
    """
    cp_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    has_partnership = draw(st.booleans())
    role = draw(st.sampled_from(["cp", "admin"]))

    return {
        "cp_id": cp_id,
        "project_id": project_id,
        "has_partnership": has_partnership,
        "role": role,
    }


@st.composite
def multi_cp_project_scenario(draw):
    """Generate a scenario with multiple CPs and projects.

    Creates a set of CPs, projects, and assignments, then picks
    a random CP-project pair to test access on.
    """
    num_cps = draw(st.integers(min_value=2, max_value=5))
    num_projects = draw(st.integers(min_value=2, max_value=5))

    cp_ids = [str(uuid.uuid4()) for _ in range(num_cps)]
    project_ids = [str(uuid.uuid4()) for _ in range(num_projects)]

    # Create a random set of partnerships
    partnerships = set()
    num_assignments = draw(st.integers(min_value=1, max_value=num_cps * num_projects))
    for _ in range(num_assignments):
        cp = draw(st.sampled_from(cp_ids))
        project = draw(st.sampled_from(project_ids))
        partnerships.add((cp, project))

    # Pick a random CP-project pair to test
    test_cp = draw(st.sampled_from(cp_ids))
    test_project = draw(st.sampled_from(project_ids))
    expected_access = (test_cp, test_project) in partnerships

    return {
        "test_cp": test_cp,
        "test_project": test_project,
        "partnerships": partnerships,
        "expected_access": expected_access,
    }


# --- Mock DB Helper ---

class MockDB:
    """A fake async DB that returns partnership or None based on configuration."""

    def __init__(self, has_partnership: bool):
        self._has_partnership = has_partnership

    async def execute(self, stmt):
        result = MagicMock()
        if self._has_partnership:
            mock_partnership = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_partnership)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result


# --- Property Tests ---


@pytest.mark.asyncio
@given(scenario=tenant_isolation_scenario())
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_tenant_isolation_access_control(scenario: dict):
    """Property 6: Access denied for unassigned projects; granted for assigned ones.

    For admin role: always granted regardless of partnership.
    For CP role: granted only if partnership exists.
    """
    cp_id = scenario["cp_id"]
    project_id = scenario["project_id"]
    has_partnership = scenario["has_partnership"]
    role = scenario["role"]

    current_user = {
        "sub": f"user-{cp_id}",
        "phone": "9876543210",
        "role": role,
        "cp_id": cp_id,
    }

    db = MockDB(has_partnership=has_partnership)

    if role == "admin":
        # Admins always get access
        result = await require_project_access(
            project_id=project_id,
            current_user=current_user,
            db=db,
        )
        assert result == current_user
    elif role == "cp" and has_partnership:
        # CP with partnership gets access
        result = await require_project_access(
            project_id=project_id,
            current_user=current_user,
            db=db,
        )
        assert result == current_user
    elif role == "cp" and not has_partnership:
        # CP without partnership gets 403
        with pytest.raises(HTTPException) as exc_info:
            await require_project_access(
                project_id=project_id,
                current_user=current_user,
                db=db,
            )
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@given(scenario=multi_cp_project_scenario())
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_multi_cp_project_isolation(scenario: dict):
    """Property 6: In a multi-CP/project setup, access is granted iff partnership exists.

    Generates random CP/project/partnership combinations and verifies
    correct access decisions for each test pair.
    """
    test_cp = scenario["test_cp"]
    test_project = scenario["test_project"]
    expected_access = scenario["expected_access"]

    current_user = {
        "sub": f"cp-{test_cp}",
        "phone": "9876543210",
        "role": "cp",
        "cp_id": test_cp,
    }

    db = MockDB(has_partnership=expected_access)

    if expected_access:
        result = await require_project_access(
            project_id=test_project,
            current_user=current_user,
            db=db,
        )
        assert result == current_user
    else:
        with pytest.raises(HTTPException) as exc_info:
            await require_project_access(
                project_id=test_project,
                current_user=current_user,
                db=db,
            )
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@given(role=st.text(min_size=1, max_size=20).filter(lambda s: s not in ("admin", "cp")))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_unknown_roles_always_denied(role: str):
    """Property 6: Unknown/unexpected roles are always denied access."""
    current_user = {
        "sub": "unknown-user",
        "phone": "9876543210",
        "role": role,
        "cp_id": str(uuid.uuid4()),
    }

    db = MockDB(has_partnership=True)  # Even with partnership, unknown role denied

    with pytest.raises(HTTPException) as exc_info:
        await require_project_access(
            project_id=str(uuid.uuid4()),
            current_user=current_user,
            db=db,
        )
    assert exc_info.value.status_code == 403
