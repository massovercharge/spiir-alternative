import re
from pathlib import Path

content = Path('backend/app/sync_service.py').read_text()

loop_orig = """
        for idx, account in enumerate(accounts, start=1):
            account_uid = account["uid"]
            params, fetch_window = _fetch_params(incremental, account_uid)
            notify(
                f"Kontrollerer tilknyttede konti ({session_name})",
                10,
                {"account_count": len(accounts), "fetch_window": fetch_window},
            )
            raw_transactions: list[dict[str, Any]] = []
            continuation_key = None
            page = 0

            while True:
                page += 1
                notify(
                    f"Henter konto {idx}/{len(accounts)} · side {page}",
                    min(75, 15 + idx * 10 + page * 3),
                    {"account_index": idx, "page_number": page, "fetch_window": fetch_window},
                )
                page_params = dict(params)
                if continuation_key:
                    page_params["continuation_key"] = continuation_key
                payload = _request_json(
                    "GET", f"/accounts/{account_uid}/transactions", params=page_params
                )
                raw_transactions.extend(payload.get("transactions", []))
                continuation_key = payload.get("continuation_key")
                if not continuation_key:
                    break

            # Fetch balances
            try:
                balance_payload = _request_json("GET", f"/accounts/{account_uid}/balances")
                balances = balance_payload.get("balances", [])
                
                preferred_balance = None
                for b_type in ["CLBD", "ITAV", "XPCD"]:
                    match = next((b for b in balances if b.get("balance_type") == b_type), None)
                    if match:
                        preferred_balance = match
                        break
                if not preferred_balance and balances:
                    preferred_balance = balances[0]
                    
                if preferred_balance:
                    from .money import to_minor
                    amt_str = str((preferred_balance.get("balance_amount") or {}).get("amount", "0"))
                    
                    with Session(engine) as inner_db:
                        db_acc = inner_db.get(Account, account_uid)
                        if db_acc:
                            db_acc.balance_minor = to_minor(amt_str)
                            inner_db.commit()
            except Exception as e:
                print(f"Failed to fetch balances for {account_uid}: {e}")

            total_fetched += len(raw_transactions)
            notify(
                f"Gemmer og normaliserer ({session_name})",
                85,
                {"transaction_count": len(raw_transactions)},
            )

            # Save raw JSON for audit trail
            _raw_dir().mkdir(parents=True, exist_ok=True)
            raw_path = _raw_dir() / f"tx_{session_name}_{account_uid}_{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
            raw_path.write_text(json.dumps({
                "fetched_at": _utcnow_iso(),
                "account": account,
                "transactions": raw_transactions,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

            new = _normalize_and_persist(account, raw_transactions, session_name)
            total_new += new
"""

loop_new = """
        account_errors = []
        for idx, account in enumerate(accounts, start=1):
            account_uid = account["uid"]
            
            try:
                params, fetch_window = _fetch_params(incremental, account_uid)
                notify(
                    f"Kontrollerer tilknyttede konti ({session_name})",
                    10,
                    {"account_count": len(accounts), "fetch_window": fetch_window},
                )
                raw_transactions: list[dict[str, Any]] = []
                continuation_key = None
                page = 0

                while True:
                    page += 1
                    notify(
                        f"Henter konto {idx}/{len(accounts)} · side {page}",
                        min(75, 15 + idx * 10 + page * 3),
                        {"account_index": idx, "page_number": page, "fetch_window": fetch_window},
                    )
                    page_params = dict(params)
                    if continuation_key:
                        page_params["continuation_key"] = continuation_key
                    payload = _request_json(
                        "GET", f"/accounts/{account_uid}/transactions", params=page_params
                    )
                    raw_transactions.extend(payload.get("transactions", []))
                    continuation_key = payload.get("continuation_key")
                    if not continuation_key:
                        break

                # Fetch balances
                try:
                    balance_payload = _request_json("GET", f"/accounts/{account_uid}/balances")
                    balances = balance_payload.get("balances", [])
                    
                    preferred_balance = None
                    for b_type in ["CLBD", "ITAV", "XPCD"]:
                        match = next((b for b in balances if b.get("balance_type") == b_type), None)
                        if match:
                            preferred_balance = match
                            break
                    if not preferred_balance and balances:
                        preferred_balance = balances[0]
                        
                    if preferred_balance:
                        from .money import to_minor
                        amt_str = str((preferred_balance.get("balance_amount") or {}).get("amount", "0"))
                        
                        with Session(engine) as inner_db:
                            db_acc = inner_db.get(Account, account_uid)
                            if db_acc:
                                db_acc.balance_minor = to_minor(amt_str)
                                inner_db.commit()
                except Exception as e:
                    print(f"Failed to fetch balances for {account_uid}: {e}")

                total_fetched += len(raw_transactions)
                notify(
                    f"Gemmer og normaliserer ({session_name})",
                    85,
                    {"transaction_count": len(raw_transactions)},
                )

                # Save raw JSON for audit trail
                _raw_dir().mkdir(parents=True, exist_ok=True)
                raw_path = _raw_dir() / f"tx_{session_name}_{account_uid}_{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
                raw_path.write_text(json.dumps({
                    "fetched_at": _utcnow_iso(),
                    "account": account,
                    "transactions": raw_transactions,
                }, indent=2, ensure_ascii=False), encoding="utf-8")

                new = _normalize_and_persist(account, raw_transactions, session_name)
                total_new += new

            except RateLimitError as e:
                print(f"Rate limit hit for {account_uid}: {e}")
                account_errors.append(f"Konto {idx} (Rate Limit)")
                continue
            except Exception as e:
                print(f"Failed to sync account {account_uid}: {e}")
                account_errors.append(f"Konto {idx} (Fejl)")
                continue
"""
content = content.replace(loop_orig.strip(), loop_new.strip())

# Add account errors to the return dictionary so the background job can save it
return_orig = """
    return {
        "fetched_count": total_fetched,
        "new_count": total_new,
        "elapsed_seconds": elapsed,
        "fetch_window": fetch_window if connections else {},
    }
"""
return_new = """
    return {
        "fetched_count": total_fetched,
        "new_count": total_new,
        "elapsed_seconds": elapsed,
        "fetch_window": fetch_window if connections else {},
        "account_errors": account_errors,
    }
"""
content = content.replace(return_orig.strip(), return_new.strip())

Path('backend/app/sync_service.py').write_text(content)
print("Phase 4 done")
