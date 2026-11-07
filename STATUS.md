# STATUS - junk-drawer-mcp-server

Built 2026-11-07 by Asdale Dynamics, LLC.

## What was built

An MCP server (stdio) that catalogues the small things that vanish:
cables, adapters, batteries, craft bits, spare keys. Local-first;
storage is a plain JSON file by default, or a single-table SQLite file
if `JUNK_DRAWER_DB` points at a `.db`/`.sqlite` path.

Items carry: name, kind (10 kinds incl. cable/adapter/battery/key),
room, container (location note), description, tags, photo_hint (what
to snap when you're next at the spot - no photos actually required),
added/updated dates, and a full move history.

### Tools

| Tool | What it answers |
| --- | --- |
| add_item | "log this before it vanishes" - validates name/kind/room |
| search | "do we have an HDMI adapter?" - plain words, token scoring leaning on name and tags, forgiving plurals |
| where_is | one item's spot, photo hint, and move log |
| list_by_room | items in a room; with no argument, rooms with counts |
| mark_moved | relocation with auto-recorded from/to history |
| move_history | every recorded hop, oldest first |
| remove_item | mark gone (used up, given away) without deleting the record |
| list_kinds / summary | kinds cheat-sheet and a calm overview |

One prompt: `find_my_thing` - a friendly step-by-step walked question
for a lost-thing moment.

Distinct from gear-serial-inventory-webapp (serial-numbered gear) and
free-home-inventory-kit (insurance printables): this is for unlabeled
small stuff and quick "where is it" moments.

## Layout

```
src/junk_drawer/{store.py,search.py,server.py}   storage, ranking, MCP server
tests/                                           58 pytest tests + fixtures
data/                                            default JSON drawer (gitignored contents, .gitkeep tracked)
```

## How to run

```bash
pip install -e .
export JUNK_DRAWER_DB=$PWD/data/drawer.json   # optional
junk-drawer-server                            # MCP over stdio
# or: python -m junk_drawer.server
```

Point an MCP client (e.g. Claude Desktop, opencode) at the command with
`JUNK_DRAWER_DB` in env. See README for the JSON snippet.

## Verification results (2026-11-07)

- `python3 -m pytest -q` - **58 passed** in ~1.5s, including:
  - store: add/find/update/move/remove validation + JSON persistence
  - sqlite: same behaviour, plain-table contents checked via sqlite3
  - search: plural-free matching, required-all-tokens, gone-item filtering
  - server tools end-to-end via `server.call_tool`, plus prompt listing
  - stdio smoke test: real subprocess + official MCP client roundtrip
    (add -> search -> list_by_room -> mark_moved -> move_history, then
    re-read the JSON file to confirm persistence)
- Entry point installed and boots: `junk-drawer-server` prints an
  mcp-2.x startup banner and speaks stdio.
- SQLite env-path run verified by hand: add + move + reload across two
  `Drawer` instances opened the same `.db`.

## Known gaps (on purpose, mostly)

- No deletion of records, only status=gone - the history is the point.
- Search is token-scored, not semantic; exact synonyms ("lightning
  cable" for USB-C) must be put in tags by the adder.
- No photo files - only hints. A future photo-map feature could pair
  hints with optional local image paths.
- No concurrent-write locking (single user, local machine expected).
- Questions like "which of my batteries are in the kitchen?" need two
  calls (search then where_is) rather than one combined filter tool.
