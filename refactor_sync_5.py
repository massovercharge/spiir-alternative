import re
from pathlib import Path

content = Path('backend/app/sync_service.py').read_text()

run_sync_orig = """
        _update_job("running", 1, "Starter hentning")
        result = retrieve_transactions(incremental=True, progress=progress)
        _update_job(
            "succeeded", 100, "Færdig",
            completed_at=_utcnow_iso(),
            result_json=json.dumps(result, default=str),
        )
"""

run_sync_new = """
        _update_job("running", 1, "Starter hentning")
        result = retrieve_transactions(incremental=True, progress=progress)
        
        account_errors = result.get("account_errors", [])
        if account_errors:
            msg = "Færdig (med fejl på " + ", ".join(account_errors) + ")"
        else:
            msg = "Færdig"
            
        _update_job(
            "succeeded" if not account_errors else "completed_with_errors", 100, msg,
            completed_at=_utcnow_iso(),
            result_json=json.dumps(result, default=str),
            error_message="Nogle konti fejlede: " + ", ".join(account_errors) if account_errors else None
        )
"""
content = content.replace(run_sync_orig.strip(), run_sync_new.strip())
Path('backend/app/sync_service.py').write_text(content)
print("Phase 5 done")
