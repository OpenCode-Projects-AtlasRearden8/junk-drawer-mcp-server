"""SQLite backend tests: same behaviour as JSON, different plumbing."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from junk_drawer.store import Drawer, DrawerError


@pytest.fixture
def sqlite_drawer(tmp_path: Path) -> Drawer:
    return Drawer(tmp_path / "drawer.db")


class TestSQLite:
    def test_add_and_reload(self, sqlite_drawer: Drawer, tmp_path: Path) -> None:
        sqlite_drawer.add_item(
            "HDMI coupler", "adapter", "office", container="tin", tags="hdmi"
        )
        reload = Drawer(tmp_path / "drawer.db")
        item = reload.items["hdmi-coupler"]
        assert item["name"] == "HDMI coupler"
        assert item["tags"] == ["hdmi"]

    def test_marks_and_history_survive_reload(
        self, sqlite_drawer: Drawer, tmp_path: Path
    ) -> None:
        sqlite_drawer.add_item("bit", "hardware", "garage")
        sqlite_drawer.mark_moved("bit", "shed", "toolbox", "moved")
        reload = Drawer(tmp_path / "drawer.db")
        assert reload.items["bit"]["room"] == "shed"
        assert reload.move_history("bit")[0]["to_room"] == "shed"

    def test_find_and_report_tools(self, sqlite_drawer: Drawer) -> None:
        sqlite_drawer.add_item("AA batteries", "battery", "kitchen")
        assert sqlite_drawer.find_item("AA batteries")["id"] == "aa-batteries"
        sqlite_drawer.remove_item("aa-batteries", reason="dead")
        assert sqlite_drawer.live_items() == []
        assert len(sqlite_drawer.gone_items()) == 1

    def test_tables_are_plain_sqlite(self, sqlite_drawer: Drawer) -> None:
        sqlite_drawer.add_item("tin pin", "other", "office")
        with sqlite3.connect(sqlite_drawer.path) as conn:
            rows = conn.execute("SELECT name, kind, room FROM items").fetchall()
        assert rows == [("tin pin", "other", "office")]

    def test_gone_items_hidden_from_find(self, sqlite_drawer: Drawer) -> None:
        sqlite_drawer.add_item("old key", "key", "hall")
        sqlite_drawer.remove_item("old-key", reason="given away")
        with pytest.raises(DrawerError):
            sqlite_drawer.remove_item("old-key", reason="again")
