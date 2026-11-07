"""Store tests: add, find, update, move, remove, validation, persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from junk_drawer.store import Drawer, DrawerError, parse_date, slugify


class TestAddItem:
    def test_adds_and_persists(self, fresh_drawer: Drawer) -> None:
        record = fresh_drawer.add_item(
            "HDMI to mini HDMI adapter",
            kind="adapter",
            room="office",
            container="tin, second drawer",
            tags="hdmi, video",
            photo_hint="left of the tape measure",
        )
        assert record["name"] == "HDMI to mini HDMI adapter"
        assert record["tags"] == ["hdmi", "video"]
        assert fresh_drawer.items[record["id"]]["container"] == "tin, second drawer"

        reload = Drawer(fresh_drawer.path)
        assert reload.items[record["id"]]["name"] == "HDMI to mini HDMI adapter"

    def test_normalizes_tags_from_string(self, fresh_drawer: Drawer) -> None:
        record = fresh_drawer.add_item("craft glue", "craft", "craft room",
                                       tags="  Glue , sewing ")
        assert record["tags"] == ["glue", "sewing"]

    def test_requires_name(self, fresh_drawer: Drawer) -> None:
        with pytest.raises(DrawerError):
            fresh_drawer.add_item("  ", kind="cable", room="office")

    def test_requires_valid_kind(self, fresh_drawer: Drawer) -> None:
        with pytest.raises(DrawerError):
            fresh_drawer.add_item("mystery thing", kind="gadget", room="office")

    def test_requires_room(self, fresh_drawer: Drawer) -> None:
        with pytest.raises(DrawerError):
            fresh_drawer.add_item("leftover bolt", kind="hardware", room="")

    def test_add_item_dedup_slugs(self, fresh_drawer: Drawer) -> None:
        first = fresh_drawer.add_item("Test thing", "other", "office")
        second = fresh_drawer.add_item("Test thing", "other", "office")
        assert first["id"] == "test-thing"
        assert second["id"] == "test-thing-2"


class TestFindItem:
    def test_by_id_and_name_case_insensitive(self, sample_drawer: Drawer) -> None:
        assert sample_drawer.find_item("spare-house-key")["room"] == "hall"
        assert sample_drawer.find_item("SPARE HOUSE KEY")["id"] == "spare-house-key"
        assert sample_drawer.find_item("spare house key")["id"] == "spare-house-key"

    def test_unique_partial_match(self, sample_drawer: Drawer) -> None:
        found = sample_drawer.find_item("craft")
        assert found is not None
        assert found["id"] == "craft-thread-red"

    def test_ambiguous_partial_misses(self, sample_drawer: Drawer) -> None:
        # 'cable' appears in two live item names - no unique match.
        assert sample_drawer.find_item("cable") is None

    def test_does_not_return_gone_items(self, sample_drawer: Drawer) -> None:
        assert sample_drawer.find_item("micro-usb-cable-red") is None


class TestUpdateItem:
    def test_updates_container(self, sample_drawer: Drawer) -> None:
        updated = sample_drawer.update_item(
            "spare-house-key", {"container": "blue fob, hook rail"}
        )
        assert updated["container"] == "blue fob, hook rail"
        assert updated["moves"] == []  # update is not a move
        assert updated["updated"] >= updated["added"]

    def test_gone_and_unknown_rejected(self, sample_drawer: Drawer) -> None:
        with pytest.raises(DrawerError):
            sample_drawer.update_item("micro-usb-cable-red", {"room": "kitchen"})
        with pytest.raises(DrawerError):
            sample_drawer.update_item("nope", {"room": "kitchen"})


class TestMoves:
    def test_mark_moved_updates_and_logs(self, sample_drawer: Drawer) -> None:
        moved = sample_drawer.mark_moved(
            "usb-c-cable-short", "lounge", "TV cabinet pouch", "rewiring"
        )
        assert moved["room"] == "lounge"
        assert moved["container"] == "TV cabinet pouch"
        assert len(moved["moves"]) == 1
        move = moved["moves"][0]
        assert move["from_room"] == "office"
        assert move["to_room"] == "lounge"
        assert move["note"] == "rewiring"
        # persisted
        reload = Drawer(sample_drawer.path)
        assert reload.items["usb-c-cable-short"]["room"] == "lounge"

    def test_same_room_without_container_is_rejected(self, fresh_drawer: Drawer) -> None:
        fresh_drawer.add_item("bit", "hardware", "garage")
        with pytest.raises(DrawerError):
            fresh_drawer.mark_moved("bit", "   ")

    def test_move_history_empty_vs_filled(self, sample_drawer: Drawer) -> None:
        assert sample_drawer.move_history("spare-house-key") == []
        sample_drawer.move_history("component-video-cable")
        sample_drawer.mark_moved("component-video-cable", "office", "back pouch")
        assert len(sample_drawer.move_history("component-video-cable")) == 2

    def test_remove_item_marks_gone_and_keeps_record(self, sample_drawer: Drawer) -> None:
        removed = sample_drawer.remove_item(
            "aa-battery-full-box", reason="used up", gone_to="doorbell"
        )
        assert removed["status"] == "gone"
        assert removed["moves"][-1]["note"] == "used up"
        assert sample_drawer.find_item("aa-battery-full-box") is None
        assert sample_drawer.gone_items() and not sum(
            1 for i in sample_drawer.live_items() if i["id"] == "aa-battery-full-box"
        )


class TestRooms:
    def test_room_counts(self, sample_drawer: Drawer) -> None:
        counts = sample_drawer.rooms()
        assert counts == {"craft room": 1, "hall": 1, "kitchen": 1,
                          "lounge": 1, "office": 2}
        assert "gone" not in counts


class TestValidationHelpers:
    def test_parse_date(self) -> None:
        assert parse_date("2026-01-05") == "2026-01-05"
        assert parse_date(None)
        with pytest.raises(DrawerError):
            parse_date("soon")

    def test_slugify(self) -> None:
        assert slugify("HDMI to mini HDMI adapter!") == "hdmi-to-mini-hdmi-adapter"
        assert slugify("///") == "item"


class TestSchemaPassthrough:
    def test_extra_fields_survive_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "drawer.json"
        payload = {"version": 1, "items": {}}
        path.write_text(json.dumps(payload), encoding="utf-8")
        drawer = Drawer(path)
        drawer.add_item("tin pin", "other", "office")
        assert json.loads(path.read_text(encoding="utf-8"))["items"]["tin-pin"]
