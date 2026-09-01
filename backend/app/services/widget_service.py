import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_data_dir
from app.schemas.widget import (
    WidgetChart,
    WidgetListItem,
    WidgetManifest,
    WidgetOutput,
    WidgetSeries,
    WidgetTable,
)

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, WidgetOutput]] = {}


def get_widgets_dir() -> Path:
    """Return root directory for user-defined widgets."""
    path = get_data_dir() / "widgets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_builtin_widgets_dir() -> Path:
    """Return directory for built-in/shipped widgets."""
    path = Path(__file__).resolve().parent.parent / "widgets_builtin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_widgets_config_path() -> Path:
    return get_data_dir() / "widgets_config.json"


def _load_config() -> dict[str, Any]:
    config_file = get_widgets_config_path()
    if not config_file.exists():
        return {"households": {}}
    try:
        with open(config_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read widgets config: {e}")
        return {"households": {}}


def _save_config(config: dict[str, Any]) -> None:
    config_file = get_widgets_config_path()
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save widgets config: {e}")


def _get_household_config(household_id: str) -> dict[str, Any]:
    cfg = _load_config()
    households = cfg.get("households", {})
    return households.get(household_id, {"enabled": {}, "order": []})


def _update_household_config(household_id: str, updates: dict[str, Any]) -> None:
    cfg = _load_config()
    if "households" not in cfg:
        cfg["households"] = {}
    current = cfg["households"].get(household_id, {"enabled": {}, "order": []})
    current.update(updates)
    cfg["households"][household_id] = current
    _save_config(cfg)


def discover_widgets() -> dict[str, tuple[WidgetManifest, Path, bool]]:
    """Scan both user and built-in widget directories.

    Returns dict mapping widget_id -> (manifest, directory_path, has_script).
    User widgets override built-in widgets with the same id.
    """
    discovered: dict[str, tuple[WidgetManifest, Path, bool]] = {}
    search_dirs = [get_builtin_widgets_dir(), get_widgets_dir()]
    alt_dir = get_data_dir().parent / "data" / "widgets"
    if alt_dir.resolve() != get_widgets_dir().resolve() and alt_dir.exists():
        search_dirs.append(alt_dir)

    for parent_dir in search_dirs:
        if not parent_dir.exists():
            continue
        for child in parent_dir.iterdir():
            if not child.is_dir():
                continue
            manifest_file = child / "widget.json"
            if not manifest_file.exists():
                continue

            try:
                with open(manifest_file, encoding="utf-8") as f:
                    data = json.load(f)
                manifest = WidgetManifest.model_validate(data)
                has_script = (child / "widget.py").exists()
                discovered[manifest.id] = (manifest, child, has_script)
            except Exception as e:
                logger.error(f"Error loading widget manifest in {child}: {e}")

    return discovered


def list_widgets(household_id: str) -> list[WidgetListItem]:
    """Return all discovered widgets with household-specific enable status and order."""
    discovered = discover_widgets()
    h_config = _get_household_config(household_id)
    enabled_map = h_config.get("enabled", {})
    order_list = h_config.get("order", [])

    items: list[WidgetListItem] = []

    for idx, widget_id in enumerate(order_list):
        if widget_id in discovered:
            manifest, _, has_script = discovered[widget_id]
            is_enabled = enabled_map.get(widget_id, manifest.default_enabled)
            items.append(
                WidgetListItem(
                    manifest=manifest,
                    is_enabled=is_enabled,
                    position=idx,
                    has_script=has_script,
                )
            )

    # Add remaining discovered widgets not in order list
    known_ids = set(order_list)
    for widget_id, (manifest, _, has_script) in discovered.items():
        if widget_id not in known_ids:
            is_enabled = enabled_map.get(widget_id, manifest.default_enabled)
            items.append(
                WidgetListItem(
                    manifest=manifest,
                    is_enabled=is_enabled,
                    position=len(items),
                    has_script=has_script,
                )
            )

    return items


def toggle_widget(household_id: str, widget_id: str, enabled: bool) -> bool:
    """Toggle a widget's enabled status for a household."""
    h_config = _get_household_config(household_id)
    enabled_map = h_config.get("enabled", {})
    enabled_map[widget_id] = enabled

    order = h_config.get("order", [])
    if widget_id not in order:
        order.append(widget_id)

    _update_household_config(household_id, {"enabled": enabled_map, "order": order})
    return enabled


def reorder_widget(household_id: str, widget_id: str, direction: str) -> list[str]:
    """Move a widget up or down in the presentation order."""
    discovered = discover_widgets()
    h_config = _get_household_config(household_id)
    order = list(h_config.get("order", []))

    # Ensure all discovered widgets are in order
    for wid in discovered:
        if wid not in order:
            order.append(wid)

    if widget_id not in order:
        return order

    idx = order.index(widget_id)
    if direction == "up" and idx > 0:
        order[idx], order[idx - 1] = order[idx - 1], order[idx]
    elif direction == "down" and idx < len(order) - 1:
        order[idx], order[idx + 1] = order[idx + 1], order[idx]

    _update_household_config(household_id, {"order": order})
    return order


def _get_active_db_path() -> Path:
    """Resolve active peng.sqlite path."""
    env_db = os.environ.get("DATABASE_URL")
    if env_db and env_db.startswith("sqlite:///"):
        clean_path = env_db.replace("sqlite:///", "")
        candidate = Path(clean_path).resolve()
        if candidate.exists():
            return candidate

    # Standard default
    candidate = get_data_dir() / "peng.sqlite"
    if candidate.exists():
        return candidate

    # Fallback to backend data or root data
    backend_candidate = Path("data/peng.sqlite").resolve()
    if backend_candidate.exists():
        return backend_candidate

    return candidate


def execute_sql_widget(manifest: WidgetManifest, household_id: str) -> WidgetOutput:
    """Safely execute a declarative SQL widget against SQLite."""
    if not manifest.sql_query:
        return WidgetOutput(
            success=False,
            error="Widget er markeret som 'sql', men mangler 'sql_query' i widget.json.",
        )

    db_path = _get_active_db_path()
    if not db_path.exists():
        return WidgetOutput(success=False, error=f"Databasen blev ikke fundet på {db_path}")

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Execute query with household parameter
        cursor.execute(manifest.sql_query, {"household_id": household_id})
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []

        data_rows = [[r[c] for c in columns] for r in rows]
        dict_rows = [dict(r) for r in rows]

        # Construct chart if columns exist
        chart: Optional[WidgetChart] = None
        if len(columns) >= 2 and len(dict_rows) > 0:
            x_col = columns[0]
            val_cols = columns[1:]
            series = [
                WidgetSeries(key=c, label=c.replace("_", " ").title(), type="bar")
                for c in val_cols
            ]
            chart = WidgetChart(chart_type="bar", x_axis=x_col, series=series, data=dict_rows)

        # Construct basic summary
        summary = f"Fandt {len(rows)} rækker."

        conn.close()
        return WidgetOutput(
            success=True,
            summary=summary,
            table=WidgetTable(columns=columns, rows=data_rows),
            chart=chart,
            computed_at=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        logger.error(f"SQL Widget execution failed: {e}", exc_info=True)
        return WidgetOutput(
            success=False,
            error=f"SQL fejl: {e!s}",
            computed_at=datetime.now(UTC).isoformat(),
        )


def execute_script_widget(
    widget_dir: Path, manifest: WidgetManifest, household_id: str
) -> WidgetOutput:
    """Execute a python script widget in an isolated, sandboxed subprocess."""
    script_file = widget_dir / "widget.py"
    if not script_file.exists():
        return WidgetOutput(
            success=False,
            error=f"Scriptfilen 'widget.py' blev ikke fundet i {widget_dir.name}.",
        )

    db_path = _get_active_db_path()

    # Sandboxed environment: strip secrets and pass clean context
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONUNBUFFERED": "1",
        "PENG_DB_PATH": str(db_path),
        "PENG_HOUSEHOLD_ID": household_id,
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
    }
    for var in ["SYSTEMROOT", "TMP", "TEMP", "VIRTUAL_ENV"]:
        if var in os.environ:
            clean_env[var] = os.environ[var]

    try:
        cmd = [sys.executable, str(script_file)]
        proc = subprocess.run(
            cmd,
            cwd=str(widget_dir),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=5.0,  # 5 seconds strict timeout
        )

        if proc.returncode != 0:
            return WidgetOutput(
                success=False,
                error=f"Scriptet afsluttede med fejlkode {proc.returncode}.",
                traceback=proc.stderr or proc.stdout,
                computed_at=datetime.now(UTC).isoformat(),
            )

        output_str = proc.stdout.strip()
        if not output_str:
            return WidgetOutput(
                success=False,
                error="Scriptet returnerede ikke noget output (forventede JSON).",
                traceback=proc.stderr,
                computed_at=datetime.now(UTC).isoformat(),
            )

        # Parse JSON output
        parsed = json.loads(output_str)
        output = WidgetOutput.model_validate(parsed)
        output.computed_at = datetime.now(UTC).isoformat()
        return output

    except subprocess.TimeoutExpired:
        return WidgetOutput(
            success=False,
            error="Scriptet overskred den tilladte tidsgrænse på 5 sekunder (Timeout).",
            computed_at=datetime.now(UTC).isoformat(),
        )
    except json.JSONDecodeError as jde:
        return WidgetOutput(
            success=False,
            error="Scriptets output kunne ikke parses som gyldig JSON.",
            traceback=f"JSONDecodeError: {jde}\nOutput received:\n{proc.stdout[:500]}",
            computed_at=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        logger.error(f"Script Widget execution failed: {e}", exc_info=True)
        return WidgetOutput(
            success=False,
            error=f"Uventet fejl under kørsel af script: {e!s}",
            computed_at=datetime.now(UTC).isoformat(),
        )


def execute_widget(
    widget_id: str, household_id: str, force_refresh: bool = False
) -> tuple[WidgetManifest, WidgetOutput]:
    """Fetch or execute a widget, utilizing cache where appropriate."""
    discovered = discover_widgets()
    if widget_id not in discovered:
        raise ValueError(f"Widget med id '{widget_id}' blev ikke fundet.")

    manifest, widget_dir, _ = discovered[widget_id]
    cache_key = f"{household_id}:{widget_id}"

    # Check cache
    if not force_refresh and cache_key in _cache:
        cached_time, cached_output = _cache[cache_key]
        if time.time() - cached_time < manifest.refresh_interval_seconds:
            return manifest, cached_output

    # Run execution based on type
    if manifest.type == "sql":
        output = execute_sql_widget(manifest, household_id)
    else:
        output = execute_script_widget(widget_dir, manifest, household_id)

    # Cache result if execution succeeded
    if output.success:
        _cache[cache_key] = (time.time(), output)

    return manifest, output


def get_active_widgets_data(
    household_id: str, force_refresh: bool = False
) -> list[dict[str, Any]]:
    """Execute and return data for all active/enabled widgets for a household."""
    all_items = list_widgets(household_id)
    active_items = [item for item in all_items if item.is_enabled]

    results: list[dict[str, Any]] = []
    for item in active_items:
        try:
            manifest, output = execute_widget(
                item.manifest.id, household_id, force_refresh=force_refresh
            )
            results.append(
                {
                    "manifest": manifest.model_dump(),
                    "output": output.model_dump(),
                    "position": item.position,
                }
            )
        except Exception as e:
            logger.error(f"Failed executing active widget {item.manifest.id}: {e}")
            results.append(
                {
                    "manifest": item.manifest.model_dump(),
                    "output": WidgetOutput(
                        success=False, error=str(e)
                    ).model_dump(),
                    "position": item.position,
                }
            )

    return results


def clear_widget_cache(widget_id: Optional[str] = None) -> None:
    """Clear memory cache for a specific widget or all widgets."""
    global _cache
    if widget_id:
        keys_to_delete = [k for k in _cache if k.endswith(f":{widget_id}")]
        for k in keys_to_delete:
            _cache.pop(k, None)
    else:
        _cache.clear()
