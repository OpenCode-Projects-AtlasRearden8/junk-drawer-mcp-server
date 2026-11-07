# Junk Drawer MCP Server

A local MCP server cataloguing the small things that vanish: cables,
adapters, batteries, craft bits, spare keys. You add an item once - with
a location note, tags and a photo hint - and after that the question
"do we have an HDMI adapter?" takes one tool call instead of twenty
minutes of opening drawers.

Distinct from:
- **gear-serial-inventory-webapp** - that one is for serial-numbered gear; this one is for unlabeled small things.
- **free-home-inventory-kit** - that one is for insurance paperwork and printables; this one is for daily "where is it" moments.

By [Asdale Dynamics, LLC](https://dylanasdale.github.io) - AI explained
like a friend would: plain English, step by step, never condescending.

## What it does

- **add_item** - catalogue a thing: name, kind (cable, adapter, battery,
  craft, key, hardware, office, medical, media, other), room, container
  note, description, tags, photo hint.
- **search** - ask in plain words: "do we have an HDMI adapter",
  "spare house key", "AA batteries". Scoring leans on name and tags;
  small plural/singular differences are forgiven.
- **where_is** - one item's full story: exact spot, photo hint, move log.
- **list_by_room** - items in one room, or (with no room) counts per room.
- **mark_moved** - record a relocation; keeps the record and reality
  agreeing, which is the whole point.
- **move_history** - every recorded hop for an item.
- **remove_item** - mark something gone (used up, given away, binned).
- **summary** - calm overview: counts by kind, moves on file.
- **list_kinds** - the kinds the drawer knows.
- Prompt: **find_my_thing** - a gentle walk through a lost-thing question.

No personal data needed, nothing leaves your machine, and photos are
not required either: the *photo_hint* field just tells future-you what
to snap (e.g. "silver coil left of the tape measure") so you can verify
at a glance.

## Quick start

```bash
pip install -e .
export JUNK_DRAWER_DB=$PWD/data/drawer.json   # optional, this is the default spot
junk-drawer-server                            # talks MCP over stdio
```

Or run as a module: `python -m junk_drawer.server`.

### Point your MCP client at it

```json
{
  "mcpServers": {
    "junk-drawer": {
      "command": "junk-drawer-server",
      "env": { "JUNK_DRAWER_DB": "/home/you/junkdrawer/drawer.json" }
    }
  }
}
```

## Storage

- Default: **plain JSON** at `data/drawer.json` (override with
  `JUNK_DRAWER_DB`).
- **SQLite**: give `JUNK_DRAWER_DB` a path ending in `.db`, `.sqlite`
  or `.sqlite3` and the server uses a single-table SQLite file instead.
  Same tools, same behaviour.

Both files are the entire state of the system: copy one and you have a
backup.

## Examples

```
add_item "HDMI to mini HDMI adapter" kind=adapter room="office" \
         container="tin, second drawer down" tags="hdmi, video" \
         photo_hint="coiled grey cable left of the tape measure"
search "do we have an HDMI adapter"
list_by_room "office"
mark_moved "hdmi-to-mini-hdmi-adapter" new_room="lounge" \
           new_container="TV cabinet, cable pouch" note="wiring the new telly"
```

## Development

```bash
pip install -e .
pip install pytest
python -m pytest          # 60+ tests, all local
```

## License

MIT - Copyright (c) 2026 Asdale Dynamics, LLC. See [LICENSE](LICENSE).
