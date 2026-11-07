"""MCP server exposing the junk drawer over stdio.

Works with `mcp` 1.x (FastMCP) and 2.x (MCPServer). Run with:

    python -m junk_drawer.server

Local-first, JSON- or SQLite-backed, beginner friendly. Not a serial
scanner for labeled gear and not an insurance home inventory - just the
small things that vanish: cables, adapters, batteries, craft bits,
spare keys.
"""

from __future__ import annotations

import os
import sys

from .search import search as rank_matches
from .store import KINDS, Drawer, DrawerError

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCP  # type: ignore

    _MCP_VERSION = "1.x"
except ImportError:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _MCP  # type: ignore

    _MCP_VERSION = "2.x"


def _default_path() -> str:
    raw = os.environ.get("JUNK_DRAWER_DB")
    if raw:
        return raw
    # Default: a data/ folder beside the package, like a small
    # shoebox the records live in. JUNK_DRAWER_DB overrides this.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "data", "drawer.json")


def build_server(drawer: Drawer | None = None):
    """Create the MCP server bound to a drawer (default path from env)."""
    drawer = drawer or Drawer(_default_path())
    server = _MCP(
        "junk-drawer",
        title="Junk Drawer",
        description=(
            "Local catalogue of the small things that vanish: cables, "
            "adapters, batteries, craft bits, spare keys. Add an item with "
            "a location note, tags and a photo hint, then search like a "
            "friend - 'do we have an HDMI adapter?' - list by room, and "
            "mark items when they move house inside yours."
        ),
    )

    @server.tool()
    def add_item(
        name: str,
        kind: str,
        room: str,
        container: str = "",
        description: str = "",
        tags: str | list[str] | None = None,
        photo_hint: str = "",
    ) -> str:
        """Catalogue one small thing before it vanishes.

        name: what you'd call it, e.g. 'HDMI to mini HDMI adapter'.
        kind: cable, adapter, battery, craft, key, hardware, office,
              medical, media or other.
        room: where it lives, e.g. 'office', 'kitchen junk drawer'.
        container: the finer spot, e.g. 'labelled tin, second drawer'.
        tags: comma-separated, e.g. 'hdmi, video, tv mount'.
        photo_hint: what a photo of its spot would show, e.g.
            'silver coil left of the tape measure'.
        """
        try:
            item = drawer.add_item(
                name, kind, room, container, description, tags, photo_hint
            )
        except DrawerError as exc:
            return f"Could not save that: {exc}"
        tag_note = f" Tags: {', '.join(item['tags'])}." if item["tags"] else ""
        hint_note = f" Photo hint: {item['photo_hint']}." if item["photo_hint"] else ""
        return (
            f"Catalogued '{item['name']}' ({item['kind']}) in {item['room']}"
            + (f", {item['container']}" if item['container'] else "")
            + f". ID: {item['id']}.{tag_note}{hint_note} "
            "Future-you says thanks."
        )

    @server.tool()
    def search(query: str) -> str:
        """Ask the drawer a question the way you'd ask a person.

        e.g. 'do we have an HDMI adapter', 'spare house key', 'AA
        batteries'. Just list the words you remember; short is fine.
        """
        try:
            results = rank_matches(drawer.live_items(), query)
        except DrawerError as exc:
            return f"Could not search: {exc}"
        if not results:
            return (
                f"Nothing matches '{query}' in the drawer yet. If you find "
                "it anyway, add_item it so this question lands better next "
                "time."
            )
        lines = [f"{len(results)} match(es) for '{query}':"]
        for item in results:
            lines.append(_one_line(item))
        return "\n".join(lines)

    @server.tool()
    def where_is(item: str) -> str:
        """The full story on one item: exact spot, picture hint, moves."""
        found = drawer.find_item(item)
        if found is None:
            return (
                f"Couldn't find '{item}'. Try search with part of the name, "
                "or list_by_room to browse."
            )
        lines = [
            f"{found['name']} ({found['kind']}) - {found['status']}",
            f"  Location: {found['room']}"
            + (f", {found['container']}" if found["container"] else ""),
        ]
        if found["description"]:
            lines.append(f"  Notes: {found['description']}")
        if found["tags"]:
            lines.append(f"  Tags: {', '.join(found['tags'])}")
        if found["photo_hint"]:
            lines.append(
                f"  Photo hint: {found['photo_hint']} "
                "(snap the spot when you're next there)"
            )
        moves = found.get("moves", [])
        if moves:
            lines.append(f"  Moved {len(moves)} time(s):")
            for move in moves:
                frm = move["from_room"]
                to = move["to_room"]
                when = move["date"]
                note = f" - {move['note']}" if move["note"] else ""
                lines.append(f"    {when}: {frm} -> {to}{note}")
        return "\n".join(lines)

    @server.tool()
    def list_by_room(room: str = "") -> str:
        """List items in one room, or with no room, show every room count."""
        if not room.strip():
            counts = drawer.rooms()
            if not counts:
                return "Nothing catalogued yet - add_item your first cable."
            lines = ["Rooms in the drawer:"]
            for name, count in counts.items():
                lines.append(f"  {name:<24} {count} item(s)")
            return "\n".join(lines)
        rows = [i for i in drawer.live_items() if i["room"] == room.strip().lower()]
        if not rows:
            known = ", ".join(drawer.rooms()) or "(none yet)"
            return f"Nothing catalogued in '{room}'. Rooms so far: {known}."
        lines = [f"{room} ({len(rows)} item(s)):"]
        for item in rows:
            lines.append(_one_line(item))
        return "\n".join(lines)

    @server.tool()
    def mark_moved(
        item: str,
        new_room: str,
        new_container: str = "",
        note: str = "",
    ) -> str:
        """Record that an item moved (new drawer, newbox, new shelf, new box).

        item: name or ID of the item, e.g. 'hdmi-to-mini-hdmi-adapter'.
        new_room: the room it lives in now; keep the same room with a
            different new_container if it only changed containers.
        note: optional 'why', e.g. 'rerouted to the TV drawer'.
        """
        found = drawer.find_item(item)
        if found is None:
            return (
                f"Couldn't find '{item}'. Check list_by_room or search for "
                "the exact name first."
            )
        try:
            moved = drawer.mark_moved(
                found["id"], new_room, new_container, note
            )
        except DrawerError as exc:
            return f"Could not record that move: {exc}"
        return (
            f"{moved['name']} now lives in {moved['room']}"
            + (f", {moved['container']}" if moved["container"] else "")
            + f". {len(moved['moves'])} move(s) on file - "
            "the record and reality agree again."
        )

    @server.tool()
    def move_history(item: str) -> str:
        """Every recorded hop for one item, oldest first."""
        found = drawer.find_item(item)
        if found is None:
            return f"Couldn't find '{item}'."
        try:
            moves = drawer.move_history(found["id"])
        except DrawerError as exc:
            return f"Could not load history: {exc}"
        if not moves:
            return f"{found['name']} has never moved: {found['room']} since day one."
        lines = [f"{found['name']} - {len(moves)} move(s):"]
        for i, move in enumerate(moves, 1):
            note = f" - {move['note']}" if move["note"] else ""
            lines.append(
                f"  {i}. {move['date']}: {move['from_room']} -> "
                f"{move['to_room']}{note}"
            )
        return "\n".join(lines)

    @server.tool()
    def remove_item(item: str, reason: str = "", gone_to: str = "") -> str:
        """Take an item out of the drawer record: used up, given away, binned.

        reason: what happened, e.g. 'battery dead', 'key given to
        house-sitter'. gone_to: optional place it went, e.g. 'sister's
        apartment'.
        """
        found = drawer.find_item(item)
        if found is None:
            return (
                f"Couldn't find '{item}'. Only mark things out you have "
                "actually dealt with."
            )
        moved = drawer.remove_item(found["id"], reason, gone_to)
        return (
            f"{moved['name']} marked gone ({moved['moves'][-1]['note']}). "
            "The drawer record stays honest."
        )

    @server.tool()
    def list_kinds() -> str:
        """The kinds of small things this drawer tracks."""
        return "Kinds the drawer knows: " + ", ".join(KINDS) + "."

    @server.tool()
    def summary() -> str:
        """A calm overview: counts by kind, busiest rooms, recent moves."""
        live = drawer.live_items()
        gone = drawer.gone_items()
        if not live:
            return (
                "The drawer is empty of records. Even one cable in "
                "add_item starts reducing the guessing."
            )
        by_kind: dict[str, int] = {}
        for item in live:
            by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
        kinds = ", ".join(f"{k} x{n}" for k, n in sorted(by_kind.items()))
        moved_files = [mv for i in live for mv in i.get("moves", [])]
        lines = [
            f"Drawer: {len(live)} item(s) live, {len(gone)} retired.",
            f"  By kind: {kinds}",
            f"  {len(moved_files)} move(s) on file across all items.",
        ]
        if moved_files:
            recent = max(moved_files, key=lambda m: m["date"])
            lines.append(f"  Last move on file: {recent['date']}.")
        else:
            lines.append("  No moves recorded yet.")
        return "\n".join(lines)

    @server.prompt()
    def find_my_thing() -> str:
        """A gentle walk through the 'do we have an HDMI adapter?' question."""
        return (
            "Help me find something that has gone missing.\n"
            "1. Ask me what I'm looking for, in my own words.\n"
            "2. Call search with the key words - 'adapter', 'hdmi', "
            "'spare key', whatever I gave you.\n"
            "3. If we get a hit, read out where_is in one friendly line.\n"
            "4. If nothing matched, offer to add_item it once I find it, "
            "so next time takes ten seconds.\n"
            "5. Keep it kind about lost things - nobody's fault, that's "
            "what the drawer record is for."
        )

    return server


def _one_line(item: dict) -> str:
    tag_bit = f" [{', '.join(item['tags'])}]" if item["tags"] else ""
    spot = f" - {item['container']}" if item["container"] else ""
    return f"  {item['name']:<32} ({item['kind']}) {item['room']}{spot}{tag_bit}"


def main() -> None:
    server = build_server()
    print(
        f"junk-drawer MCP server ({_MCP_VERSION}) starting on stdio... "
        "local catalogue of the things that vanish",
        file=sys.stderr,
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
