"""Shared fixtures for backend tests."""
import pytest

from app.database import current_household_id

# A stable household_id used across all test fixtures.
# This avoids NOT NULL constraint failures on models that require household_id.
TEST_HOUSEHOLD_ID = "test-household-001"


@pytest.fixture(autouse=True)
def _set_household_context():
    """Set the current_household_id ContextVar so the before_insert listener
    automatically assigns household_id to all models during tests."""
    token = current_household_id.set(TEST_HOUSEHOLD_ID)
    yield
    current_household_id.reset(token)
