import pytest
from sqlmodel import SQLModel

import app.models
from app.models import current_household_id

test_engine = app.models.all_models.engine
SQLModel.metadata.create_all(test_engine)

# A stable household_id used across all test fixtures.
# This avoids NOT NULL constraint failures on models that require household_id.
TEST_HOUSEHOLD_ID = "test-household-001"

@pytest.fixture(autouse=True)
def _set_household_context():
    with test_engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())

        conn.execute(
            SQLModel.metadata.tables["household"].insert().values(
                id=TEST_HOUSEHOLD_ID,
                name="Test Household",
                inbound_email_token="default_test_token",
                created_at="2026-01-01T00:00:00Z",
            )
        )

    from app.services.category_service import seed_categories
    seed_categories()

    """Set the current_household_id ContextVar so the before_insert listener
    automatically assigns household_id to all models during tests."""
    token = current_household_id.set(TEST_HOUSEHOLD_ID)
    yield
    current_household_id.reset(token)
