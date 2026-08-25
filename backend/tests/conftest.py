import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import app.models

# Patch engine AT MODULE LOAD TIME before services are imported
sqlite_url = "sqlite:///:memory:"
test_engine = create_engine(
    sqlite_url,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False}
)
SQLModel.metadata.create_all(test_engine)

app.models.engine = test_engine
app.models.all_models.engine = test_engine

from app.models import current_household_id

# A stable household_id used across all test fixtures.
# This avoids NOT NULL constraint failures on models that require household_id.
TEST_HOUSEHOLD_ID = "test-household-001"

@pytest.fixture(autouse=True)
def _set_household_context():
    with test_engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())

    """Set the current_household_id ContextVar so the before_insert listener
    automatically assigns household_id to all models during tests."""
    token = current_household_id.set(TEST_HOUSEHOLD_ID)
    yield
    current_household_id.reset(token)
