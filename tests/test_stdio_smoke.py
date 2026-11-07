"""Stdio smoke test: boot the real server as a subprocess and talk MCP to it.

Uses the official `mcp` client against a throwaway drawer JSON file.
Skipped cleanly if the client pieces are unavailable in the installed SDK.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.client")

from mcp.client import Client, stdio  # noqa: E402


@pytest.fixture
def stdio_setup(tmp_path: Path):
    drawer_path = tmp_path / "smoke.json"
    params = stdio.StdioServerParameters(
        command=sys.executable,
        args=["-m", "junk_drawer.server"],
        env={**os.environ, "JUNK_DRAWER_DB": str(drawer_path)},
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    return params, drawer_path


def test_stdio_roundtrip(stdio_setup) -> None:
    params, drawer_path = stdio_setup

    async def main() -> str:
        async with Client(params) as client:
            listing = await client.list_tools()
            tools = listing.tools
            names = {t.name for t in tools}
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
            added = await client.call_tool(
                "add_item",
                {
                    "name": "HDMI to mini HDMI adapter",
                    "kind": "adapter",
                    "room": "office",
                    "container": "tin, second drawer down",
                    "tags": "hdmi, video",
                    "photo_hint": "coiled grey cable left of the tape measure",
                },
            )
            search = await client.call_tool(
                "search", {"query": "do we have an HDMI adapter?"}
            )
            rooms = await client.call_tool("list_by_room", {"room": "office"})
            moved = await client.call_tool(
                "mark_moved",
                {
                    "item": "HDMI to mini HDMI adapter",
                    "new_room": "lounge",
                    "new_container": "TV cabinet, cable pouch",
                    "note": "wiring the new telly",
                },
            )
            history = await client.call_tool(
                "move_history", {"item": "HDMI to mini HDMI adapter"}
            )
        return "\n".join(
            c.content[0].text  # type: ignore[union-attr,index]
            for c in (added, search, rooms, moved, history)
        )

    text = asyncio.run(main())
    assert "Catalogued 'HDMI to mini HDMI adapter'" in text
    assert "1 match(es)" in text and "office" in text
    assert "now lives in lounge" in text
    assert "office -> lounge" in text

    data = json.loads(drawer_path.read_text(encoding="utf-8"))
    item = data["items"]["hdmi-to-mini-hdmi-adapter"]
    assert item["room"] == "lounge"
    assert item["moves"][0]["note"] == "wiring the new telly"
    assert item["photo_hint"].startswith("coiled grey cable")
