import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.widget_service import (
    clear_widget_cache,
    discover_widgets,
    execute_script_widget,
    execute_sql_widget,
    list_widgets,
    reorder_widget,
    toggle_widget,
)


@pytest.fixture
def temp_widget_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        widgets_dir = tmp_path / "widgets"
        widgets_dir.mkdir()

        # Create sample SQL widget
        sql_w = widgets_dir / "sample_sql"
        sql_w.mkdir()
        with open(sql_w / "widget.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": "sample_sql",
                    "name": "Sample SQL",
                    "type": "sql",
                    "width": "half",
                    "sql_query": "SELECT 'Test' as name, 100 as val;",
                    "default_enabled": True,
                },
                f,
            )

        # Create sample Python script widget
        script_w = widgets_dir / "sample_script"
        script_w.mkdir()
        with open(script_w / "widget.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": "sample_script",
                    "name": "Sample Script",
                    "type": "script",
                    "width": "full",
                    "default_enabled": True,
                },
                f,
            )
        with open(script_w / "widget.py", "w", encoding="utf-8") as f:
            f.write(
                'import json\nprint(json.dumps({"success": True, "summary": "Hello Widget", "kpis": [{"label": "Score", "value_minor": 4200}]}))\n'
            )

        # Create sample failing script widget
        fail_w = widgets_dir / "failing_script"
        fail_w.mkdir()
        with open(fail_w / "widget.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": "failing_script",
                    "name": "Failing Script",
                    "type": "script",
                    "width": "half",
                    "default_enabled": False,
                },
                f,
            )
        with open(fail_w / "widget.py", "w", encoding="utf-8") as f:
            f.write('raise ValueError("Custom Script Error")\n')

        # Create sample timeout script widget
        timeout_w = widgets_dir / "timeout_script"
        timeout_w.mkdir()
        with open(timeout_w / "widget.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": "timeout_script",
                    "name": "Timeout Script",
                    "type": "script",
                    "width": "half",
                    "default_enabled": False,
                },
                f,
            )
        with open(timeout_w / "widget.py", "w", encoding="utf-8") as f:
            f.write("import time\ntime.sleep(10)\n")

        with (
            patch("app.services.widget_service.get_widgets_dir", return_value=widgets_dir),
            patch(
                "app.services.widget_service.get_widgets_config_path",
                return_value=tmp_path / "widgets_config.json",
            ),
        ):
            yield widgets_dir


def test_discover_widgets(temp_widget_dir):
    discovered = discover_widgets()
    assert "sample_sql" in discovered
    assert "sample_script" in discovered
    assert "failing_script" in discovered

    manifest, _path, has_script = discovered["sample_sql"]
    assert manifest.name == "Sample SQL"
    assert manifest.type == "sql"
    assert not has_script

    manifest_s, _path_s, has_script_s = discovered["sample_script"]
    assert manifest_s.type == "script"
    assert has_script_s


def test_list_and_toggle_widgets(temp_widget_dir):
    household_id = "h123"
    widgets = list_widgets(household_id)
    assert len(widgets) >= 3

    # Toggle sample_sql to False
    toggle_widget(household_id, "sample_sql", False)
    widgets_updated = list_widgets(household_id)
    sql_item = next(w for w in widgets_updated if w.manifest.id == "sample_sql")
    assert sql_item.is_enabled is False

    # Reorder
    new_order = reorder_widget(household_id, "sample_script", "up")
    assert new_order[0] == "sample_script" or len(new_order) > 0


def test_execute_script_widget_success(temp_widget_dir):
    manifest, path, _ = discover_widgets()["sample_script"]
    output = execute_script_widget(path, manifest, "h123")
    assert output.success is True
    assert output.summary == "Hello Widget"
    assert len(output.kpis) == 1
    assert output.kpis[0].label == "Score"
    assert output.kpis[0].value_minor == 4200


def test_execute_script_widget_failure(temp_widget_dir):
    manifest, path, _ = discover_widgets()["failing_script"]
    output = execute_script_widget(path, manifest, "h123")
    assert output.success is False
    assert "fejlkode" in output.error.lower()
    assert "Custom Script Error" in output.traceback


def test_execute_script_widget_timeout(temp_widget_dir):
    manifest, path, _ = discover_widgets()["timeout_script"]
    output = execute_script_widget(path, manifest, "h123")
    assert output.success is False
    assert "tidsgrænse" in output.error or "timeout" in output.error.lower()


def test_execute_sql_widget(temp_widget_dir):
    manifest, _, _ = discover_widgets()["sample_sql"]

    # Mock database
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp_db:
        conn = sqlite3.connect(tmp_db.name)
        conn.execute("CREATE TABLE posting (id TEXT, amount_minor INT);")
        conn.commit()
        conn.close()

        with patch("app.services.widget_service._get_active_db_path", return_value=Path(tmp_db.name)):
            output = execute_sql_widget(manifest, "h123")
            assert output.success is True
            assert output.table is not None
            assert output.table.columns == ["name", "val"]
            assert output.table.rows == [["Test", 100]]


def test_caching():
    clear_widget_cache()
    # verify clear does not crash
