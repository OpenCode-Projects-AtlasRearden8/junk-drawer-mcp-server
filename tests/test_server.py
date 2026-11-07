"""Tests for the MCP server: tools and prompt end-to-end with fixtures."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from junk_drawer.server import build_server
from junk_drawer.store import Drawer


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def tool_text(result: Any) -> str:
    assert result.is_error is False, result
    return result.content[0].text  # type: ignore[union-attr]


@pytest.fixture
def server(empty_drawer: Drawer):
    return build_server(empty_drawer)


@pytest.fixture
def sample_server(sample_drawer: Drawer):
    return build_server(sample_drawer)


class TestToolListing:
    def test_all_tools_listed(self, server) -> None:
        names = {t.name for t in run(server.list_tools())}
        assert {
            "add_item",
            "search",
            "where_is",
            "list_by_room",
            "mark_moved",
            "move_history",
            "remove_item",
            "list_kinds",
            "summary",
        } <= names

    def test_prompt_listed(self, server) -> None:
        names = {p.name for p in run(server.list_prompts())}
        assert "find_my_thing" in names


class TestAddItem:
    def test_adds_and_persists(self, server, empty_drawer: Drawer) -> None:
        text = tool_text(
            run(
                server.call_tool(
                    "add_item",
                    {
                        "name": "leftover bolt",
                        "kind": "hardware",
                        "room": "garage",
                        "container": " Nut pot",
                        "tags": "m6",
                    },
                )
            )
        )
        assert "Catalogued 'leftover bolt'" in text
        assert "Nut pot" in text
        assert empty_drawer.items["leftover-bolt"]["tags"] == ["m6"]

    def test_validation_error_is_friendly(self, server) -> None:
        text = tool_text(
            run(server.call_tool("add_item", {"name": "x", "kind": "", "room": ""}))
        )
        assert text.startswith("Could not save that:")
        assert "kind must be one of" in text


class TestSearch:
    def test_plain_question(self, sample_server) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "search", {"query": "do we have an HDMI adapter?"}
                )
            )
        )
        assert "1 match(es)" in text
        assert "HDMI to mini HDMI adapter" in text
        assert "office" in text

    def test_no_match_gentle(self, server) -> None:
        tool_text(
            run(
                server.call_tool(
                    "add_item",
                    {"name": "screw", "kind": "hardware", "room": "garage"},
                )
            )
        )
        text = tool_text(run(server.call_tool("search", {"query": "ribbon"})))
        assert "Nothing matches" in text
        assert "add_item" in text

    def test_matches_ranked_and_gone_hidden(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("search", {"query": "usb cable"}))
        )
        assert "USB-C cable" in text
        assert "Micro USB" not in text  # gone item nowhere

    def test_search_by_room_word_hits_location(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("search", {"query": "hall"})))
        assert "Spare house key" in text


class TestWhereIs:
    def test_full_story(self, sample_server) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "where_is", {"item": "HDMI to mini HDMI adapter"}
                )
            )
        )
        assert "tin, second drawer down" in text
        assert "Photo hint: coiled grey cable" in text
        assert "Moved 1 time(s)" in text

    def test_unknown_item(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("where_is", {"item": "ghost"})))
        assert "Couldn't find 'ghost'" in text


class TestRooms:
    def test_no_arg_lists_rooms(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("list_by_room", {})))
        for word in ("office", "hall", "kitchen", "2 item(s)"):
            assert word in text

    def test_room_listing(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("list_by_room", {"room": "office"}))
        )
        assert "office (2 item(s))" in text
        assert "USB-C cable" in text

    def test_unknown_room(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("list_by_room", {"room": "attic"}))
        )
        assert "Nothing catalogued in 'attic'" in text


class TestMoves:
    def test_mark_moved_roundtrip(self, sample_server, sample_drawer) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "mark_moved",
                    {
                        "item": "spare house key",
                        "new_room": "kitchen",
                        "new_container": "junk drawer, top",
                        "note": "temporarily",
                    },
                )
            )
        )
        assert "Spare house key now lives in kitchen" in text
        assert sample_drawer.items["spare-house-key"]["room"] == "kitchen"
        recover = tool_text(
            run(sample_server.call_tool("where_is", {"item": "spare-house-key"}))
        )
        assert "hall -> kitchen" in recover

    def test_missing_room_rejected(self, sample_server) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "mark_moved", {"item": "USB-C cable", "new_room": "  "}
                )
            )
        )
        assert "Could not record that move" in text

    def test_history(self, sample_server) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "move_history", {"item": "component video cable"}
                )
            )
        )
        assert "1 move(s)" in text
        assert "office -> lounge" in text
        assert "kept with the TV they serve" in text

    def test_history_never_moved(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("move_history", {"item": "spare house key"}))
        )
        assert "has never moved" in text


class TestRemove:
    def test_remove_marks_gone(self, sample_server, sample_drawer) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "remove_item",
                    {"item": "aa batteries", "reason": "used up in the doorbell"},
                )
            )
        )
        assert "batteries" in text.lower()
        assert "used up in the doorbell" in text
        assert sample_drawer.items["aa-battery-full-box"]["status"] == "gone"


class TestKindsAndSummary:
    def test_list_kinds(self, server) -> None:
        text = tool_text(run(server.call_tool("list_kinds", {})))
        assert "battery" in text and "adapter" in text

    def test_summary_counts(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("summary", {})))
        assert "6 item(s) live" in text
        assert "1 retired" in text
        assert "2 move(s) on file" in text

    def test_summary_empty(self, server) -> None:
        text = tool_text(run(server.call_tool("summary", {})))
        assert "empty of records" in text


class TestPrompt:
    def test_find_my_thing_text(self, server) -> None:
        got = run(server.get_prompt("find_my_thing"))
        assert "Call search" in got.messages[0].content.text  # type: ignore[index]
