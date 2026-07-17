from unittest.mock import MagicMock, patch

from app.database import current_household_id
from app.sync_service import SyncJob, start_sync_job


def test_start_sync_job_populates_household():
    """
    Test that start_sync_job correctly reads the household context
    and injects it into the SyncJob object before saving to the DB,
    and successfully passes it to the background thread.
    """
    # 1. Simulate the FastAPI Dependency setting the household context
    test_hh_id = "mocked-household-123"
    current_household_id.set(test_hh_id)

    # 2. Mock external dependencies to avoid database locks
    # We mock _run_sync_job so the thread completes instantly without doing any real work
    with (
        patch("app.sync_service.Session") as mock_session_patch,
        patch("app.sync_service._run_sync_job") as mock_run_sync_job,
    ):
        # Setup the mock DB session
        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.result_json = None
        mock_job.started_at = "2026-07-01T12:00:00Z"
        mock_job.completed_at = None
        mock_job.progress = 0
        mock_job.current_phase = "queued"
        mock_job.error_message = None
        mock_db.get.return_value = mock_job
        mock_db.exec.return_value.first.return_value = mock_job
        mock_session_patch.return_value.__enter__.return_value = mock_db

        # 3. Trigger the sync job
        res = start_sync_job()

        assert res is not None
        assert "status" in res

        # 4. Verify that db.add was called with a SyncJob containing the right household_id
        assert mock_db.add.called
        added_job = mock_db.add.call_args[0][0]
        assert isinstance(added_job, SyncJob)
        assert added_job.household_id == test_hh_id

        # Wait for the mocked thread to finish
        from app.sync_service import _RETRIEVE_STATE

        t = _RETRIEVE_STATE.get("thread")
        if t:
            t.join(timeout=2.0)

        # 5. Verify the background thread target was called with the household_id
        assert mock_run_sync_job.called
        thread_args = mock_run_sync_job.call_args[0]
        assert len(thread_args) == 2
        assert thread_args[1] == test_hh_id
