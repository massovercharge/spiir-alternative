import re
from pathlib import Path

path = Path("backend/app/bank_service.py")
content = path.read_text(encoding="utf-8")

# Add database init logic to the top, right after `import requests`
content = content.replace("import requests\n", "import requests\n\nfrom sqlmodel import select\nfrom .database import engine, BankTransaction, BankOverride, BankAccount, get_session, create_db_and_tables\n\ncreate_db_and_tables()\n")

# Replace _load_overrides
load_overrides_new = """def _load_overrides() -> dict[str, Any]:
    with next(get_session()) as db:
        overrides = db.exec(select(BankOverride)).all()
        return {
            "schema_version": "1.0",
            "updated_at": _iso_utc_now(),
            "transactions": {ov.id: ov.patch for ov in overrides}
        }
"""
content = re.sub(r'def _load_overrides\(\) -> dict\[str, Any\]:.*?(?=def _sanitize_category)', load_overrides_new, content, flags=re.DOTALL)

# Replace _load_processed
load_processed_new = """def _load_processed() -> dict[str, Any]:
    with next(get_session()) as db:
        accounts = [acc.payload for acc in db.exec(select(BankAccount)).all()]
        transactions = [tx.payload for tx in db.exec(select(BankTransaction).order_by(BankTransaction.booking_date.desc(), BankTransaction.entry_reference.desc())).all()]
        return {
            "generated_at": _iso_utc_now(),
            "last_retrieved_at": None,
            "last_retrieve_duration_seconds": None,
            "transaction_count": len(transactions),
            "accounts": accounts,
            "transactions": transactions,
        }
"""
content = re.sub(r'def _load_processed\(\) -> dict\[str, Any\]:.*?(?=def _merge_raw_payload)', load_processed_new, content, flags=re.DOTALL)

# Replace _merge_raw_payload
merge_raw_payload_new = """def _merge_raw_payload(raw_payload: dict[str, Any], session_name: str = "default") -> dict[str, Any]:
    account = raw_payload.get("account") or {}
    normalized = [_normalize_transaction(account, transaction) for transaction in raw_payload.get("transactions", [])]
    
    with next(get_session()) as db:
        uid = str(account.get("uid") or account.get("identification_hash") or account.get("account_id", {}).get("iban") or "unknown")
        db_account = db.get(BankAccount, uid)
        if not db_account:
            db_account = BankAccount(uid=uid, session_name=session_name, payload=account)
            db.add(db_account)
        else:
            db_account.payload = account
            
        for tx in normalized:
            db_tx = db.get(BankTransaction, tx["id"])
            if not db_tx:
                db_tx = BankTransaction(
                    id=tx["id"],
                    account_key=uid,
                    session_name=session_name,
                    booking_date=tx.get("booking_date") or "",
                    entry_reference=tx.get("entry_reference") or "",
                    payload=tx
                )
                db.add(db_tx)
            else:
                db_tx.payload = tx
                
        db.commit()
    
    return _load_processed()
"""
content = re.sub(r'def _merge_raw_payload\(raw_payload: dict\[str, Any\]\) -> dict\[str, Any\]:.*?(?=def _latest_processed_booking_date)', merge_raw_payload_new, content, flags=re.DOTALL)

# Replace save_bank_overrides
save_bank_overrides_new = """def save_bank_overrides(transaction_ids: list[str], patch: dict[str, Any]) -> dict[str, Any]:
    if not transaction_ids:
        raise ValueError("No Bank transactions selected")
    category = _sanitize_category(patch.get("category"))
    
    with next(get_session()) as db:
        for transaction_id in transaction_ids:
            override = db.get(BankOverride, transaction_id)
            if not override:
                override = BankOverride(id=transaction_id, updated_at=_iso_utc_now(), patch={})
                db.add(override)
                
            current = override.patch
            
            if "category" in patch:
                if category is None:
                    current.pop("category", None)
                else:
                    current["category"] = category
            if "booking_date" in patch:
                booking_date = str(patch.get("booking_date") or "").strip()
                if booking_date:
                    current["booking_date"] = booking_date
                else:
                    current.pop("booking_date", None)
            if "note" in patch:
                current["note"] = str(patch.get("note") or "")
            if "hashtags" in patch:
                requested_hashtags = _normalize_hashtags(patch.get("hashtags"))
                removed_hashtags = [tag for tag in _normalize_hashtags(current.get("hashtags")) if tag not in requested_hashtags]
                current["note"] = _append_hashtags_to_comment(
                    _remove_hashtags_from_comment(current.get("note"), removed_hashtags),
                    requested_hashtags,
                )
                current["hashtags"] = _normalize_hashtags([*_extract_hashtags(current.get("note")), *requested_hashtags])
            if "append_hashtags" in patch:
                current["note"] = _append_hashtags_to_comment(current.get("note"), patch.get("append_hashtags"))
                current["hashtags"] = _normalize_hashtags([*_normalize_hashtags(current.get("hashtags")), *_extract_hashtags(current.get("note"))])
            if "remove_hashtags" in patch:
                removed_hashtags = _normalize_hashtags(patch.get("remove_hashtags"))
                removed_hashtag_set = set(removed_hashtags)
                current["note"] = _remove_hashtags_from_comment(current.get("note"), removed_hashtags)
                current["hashtags"] = [
                    tag for tag in _normalize_hashtags([*_normalize_hashtags(current.get("hashtags")), *_extract_hashtags(current.get("note"))])
                    if tag not in removed_hashtag_set
                ]
            if any(key in patch for key in ("note", "hashtags", "append_hashtags")):
                current["hashtags"] = _extract_hashtags(current.get("note"))
            if "is_extraordinary" in patch:
                current["is_extraordinary"] = bool(patch.get("is_extraordinary"))
            if "splits" in patch:
                current["splits"] = [split for item in patch.get("splits") or [] if (split := _sanitize_split(item)) is not None]
                
            override.patch = current
            override.updated_at = _iso_utc_now()
            
        db.commit()
    
    return {"updated_count": len(transaction_ids), "updated_at": _iso_utc_now()}
"""
content = re.sub(r'def save_bank_overrides\(transaction_ids: list\[str\], patch: dict\[str, Any\]\) -> dict\[str, Any\]:.*?(?=def retrieve_bank_transactions)', save_bank_overrides_new, content, flags=re.DOTALL)

# Refactor retrieve_bank_transactions
retrieve_bank_transactions_new = """def retrieve_bank_transactions(
    *,
    incremental: bool = True,
    progress: Callable[[str, int, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    started = dt.datetime.now(dt.UTC)
    def notify(label: str, progress_value: int, extra: dict[str, Any] | None = None) -> None:
        if progress is not None:
            progress(label, progress_value, extra)

    notify("Læser Enable Banking-sessioner", 5, None)
    session_files = list(_enablebanking_dir().glob("session_*.json"))
    if not session_files:
        raise FileNotFoundError("Missing Enable Banking session. Re-authorize account access first.")
    
    all_transactions = 0
    raw_outputs: list[Path] = []
    
    for session_file in session_files:
        session = _read_json(session_file)
        session_name = session_file.stem
        accounts = session.get("accounts") or []
        if not accounts:
            continue

        params, fetch_window = _retrieve_params_for_existing_data(incremental=incremental)
        notify(f"Kontrollerer tilknyttede konti ({session_name})", 10, {"account_count": len(accounts), "fetch_window": fetch_window})
        
        for account_index, account in enumerate(accounts, start=1):
            account_uid = account["uid"]
            transactions: list[dict[str, Any]] = []
            continuation_key = None
            page_number = 0
            while True:
                page_number += 1
                notify(
                    f"Henter konto {account_index} af {len(accounts)} [{session_name}] · side {page_number}",
                    min(75, 15 + account_index * 10 + page_number * 3),
                    {"account_index": account_index, "account_count": len(accounts), "page_number": page_number, "fetch_window": fetch_window},
                )
                page_params = dict(params)
                if continuation_key:
                    page_params["continuation_key"] = continuation_key
                payload = _request_json("GET", f"/accounts/{account_uid}/transactions", params=page_params)
                transactions.extend(payload.get("transactions", []))
                continuation_key = payload.get("continuation_key")
                if not continuation_key:
                    break

            raw_payload = {
                "fetched_at": _iso_utc_now(),
                "session_id": session.get("session_id"),
                "account": account,
                "params": params,
                "transaction_count": len(transactions),
                "transactions": transactions,
            }
            notify(f"Gemmer rå bank-data ({session_name})", 78, {"account_index": account_index, "transaction_count": len(transactions), "fetch_window": fetch_window})
            out_path = _raw_dir() / f"transactions_{session_name}_{account_uid}_{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
            _write_json(out_path, raw_payload)
            raw_outputs.append(out_path)
            all_transactions += len(transactions)
            notify(f"Normaliserer og fletter bank-data ({session_name})", 86, {"transaction_count": len(transactions), "fetch_window": fetch_window})
            _merge_raw_payload(raw_payload, session_name=session_name)

    elapsed_seconds = (dt.datetime.now(dt.UTC) - started).total_seconds()
    processed = _load_processed()
    processed["last_retrieve_duration_seconds"] = round(elapsed_seconds, 3)
    # the processed flat file is no longer strictly necessary but we keep it for backward compatibility if needed, or skip it
    _write_json(_processed_file(), processed)
    notify("Bank-hentning færdig", 92, {"retrieved_count": all_transactions, "transaction_count": processed["transaction_count"], "fetch_window": fetch_window})
    return {
        "retrieved_count": all_transactions,
        "transaction_count": processed["transaction_count"],
        "raw_files": [str(path) for path in raw_outputs],
        "last_retrieved_at": processed.get("last_retrieved_at"),
        "last_retrieve_duration_seconds": processed.get("last_retrieve_duration_seconds"),
        "fetch_window": fetch_window,
    }
"""
content = re.sub(r'def retrieve_bank_transactions\(.*?\) -> dict\[str, Any\]:.*?(?=def get_bank_retrieve_status)', retrieve_bank_transactions_new, content, flags=re.DOTALL)

path.write_text(content, encoding="utf-8")
