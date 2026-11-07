"""Storage for the junk drawer: plain JSON by default, optional SQLite.

Local-first: every byte stays on this machine. No personal data is
required - but any data you do enter never leaves your disk.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

ITEM_FIELDS = (
    "name",
    "kind",
    "room",
    "container",
    "description",
    "tags",
    "photo_hint",
)

KINDS = (
    "cable",
    "adapter",
    "battery",
    "craft",
    "key",
    "hardware",
    "office",
    "medical",
    "media",
    "other",
)

STATUSES = ("live", "gone")

_SCHEMA_VERSION = 1


class DrawerError(Exception):
    """Raised for user-fixable problems (bad input, unknown item)."""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "item"


def today() -> str:
    return date.today().isoformat()


def parse_date(raw: str | None) -> str:
    """Validate an optional YYYY-MM-DD string."""
    if raw is None or not raw.strip():
        return today()
    text = raw.strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise DrawerError(f"'{text}' is not a YYYY-MM-DD date.") from exc


def _norm_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = value
    else:
        parts = re.split(r"[,;\n]", value)
    return [p.strip().lower() for p in parts if p.strip()]


class Drawer:
    """The catalogue itself, backed by JSON or SQLite.

    Choose a backend by giving a path with a matching extension
    (.json -> JSON, .db/.sqlite/.sqlite3 -> SQLite). The environment
    variable JUNK_DRAWER_DB overrides the default location.
    """

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or self._default_path())
        backend = "json"
        if self.path.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
            backend = "sqlite"
        self.backend = backend
        self._items: dict[str, dict[str, Any]] = {}
        if backend == "json":
            self._load_json()
        else:
            self._load_sqlite()

    # ------------------------------------------------------------- paths
    @staticmethod
    def _default_path() -> Path:
        raw = os.environ.get("JUNK_DRAWER_DB")
        if raw:
            return Path(raw)
        return Path(__file__).resolve().parent.parent / "data" / "drawer.json"

    # ------------------------------------------------------------ json io
    def _load_json(self) -> None:
        if self.path.exists():
            try:
                raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise DrawerError(f"Could not read {self.path}: {exc}") from exc
            items = raw.get("items", {})
            corrupt = [
                k
                for k, v in items.items()
                if not isinstance(v, dict) or not v.get("name")
            ]
            if corrupt:
                raise DrawerError(
                    f"{self.path} has item records without a name: "
                    + ", ".join(sorted(corrupt)[:5])
                )
        else:
            items = {}
        self._items = items

    def _save_json(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": _SCHEMA_VERSION, "items": self._items}
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    # --------------------------------------------------------- sqlite io
    def _open_sqlite(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS items ("
            " id TEXT PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " room TEXT NOT NULL,"
            " container TEXT NOT NULL,"
            " description TEXT NOT NULL,"
            " tags TEXT NOT NULL,"
            " photo_hint TEXT NOT NULL,"
            " added TEXT NOT NULL,"
            " updated TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " moves TEXT NOT NULL)"
        )
        return conn

    def _load_sqlite(self) -> None:
        with self._open_sqlite() as conn:
            rows = conn.execute("SELECT * FROM items").fetchall()
        self._items = {row[0]: self._row_to_item(row) for row in rows}

    @staticmethod
    def _row_to_item(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "name": row[1],
            "kind": row[2],
            "room": row[3],
            "container": row[4],
            "description": row[5],
            "tags": json.loads(row[6]),
            "photo_hint": row[7],
            "added": row[8],
            "updated": row[9],
            "status": row[10],
            "moves": json.loads(row[11]),
        }

    def _save_sqlite(self) -> None:
        with self._open_sqlite() as conn:
            conn.execute("DELETE FROM items")
            for item in self._items.values():
                conn.execute(
                    "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item["id"],
                        item["name"],
                        item["kind"],
                        item["room"],
                        item["container"],
                        item["description"],
                        json.dumps(item["tags"]),
                        item["photo_hint"],
                        item["added"],
                        item["updated"],
                        item["status"],
                        json.dumps(item["moves"]),
                    ),
                )

    # ------------------------------------------------------------- shared
    def save(self) -> None:
        if self.backend == "json":
            self._save_json()
        else:
            self._save_sqlite()

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        return self._items

    def live_items(self) -> list[dict[str, Any]]:
        out = [i for i in self._items.values() if i.get("status", "live") == "live"]
        return sorted(out, key=lambda i: (i["room"], i["name"]))

    def gone_items(self) -> list[dict[str, Any]]:
        out = [i for i in self._items.values() if i.get("status") == "gone"]
        return sorted(out, key=lambda i: (i["updated"], i["name"]))

    def _validate(self, fields: dict[str, Any]) -> dict[str, Any]:
        name = str(fields.get("name", "")).strip()
        if not name:
            raise DrawerError("An item needs a name, even a rough one.")
        kind = str(fields.get("kind", "")).strip().lower()
        if kind not in KINDS:
            raise DrawerError(
                f"kind must be one of: {', '.join(KINDS)} (got '{kind or '-'}')."
            )
        room = str(fields.get("room", "")).strip()
        if not room:
            raise DrawerError("Give a room (or 'unknown' if you truly can't say).")
        return {
            "name": name,
            "kind": kind,
            "room": room,
            "container": str(fields.get("container", "")).strip(),
            "description": str(fields.get("description", "")).strip(),
            "tags": _norm_list(fields.get("tags")),
            "photo_hint": str(fields.get("photo_hint", "")).strip(),
        }

    # ------------------------------------------------------------- add
    def add_item(
        self,
        name: str,
        kind: str,
        room: str,
        container: str = "",
        description: str = "",
        tags: str | list[str] | None = None,
        photo_hint: str = "",
    ) -> dict[str, Any]:
        """Log one small thing so future-you can find it again."""
        clean = self._validate(
            {
                "name": name,
                "kind": kind,
                "room": room,
                "container": container,
                "description": description,
                "tags": tags,
                "photo_hint": photo_hint,
            }
        )
        base = slugify(clean["name"])
        item_id = base
        n = 2
        while item_id in self._items:
            item_id = f"{base}-{n}"
            n += 1
        stamp = today()
        record = {
            "id": item_id,
            **clean,
            "added": stamp,
            "updated": stamp,
            "status": "live",
            "moves": [],
        }
        self._items[item_id] = record
        self.save()
        return record

    # ------------------------------------------------------------ lookup
    def find_item(self, name_or_id: str) -> dict[str, Any] | None:
        """Find a live item by exact id, exact name, or case-insensitive name."""
        needle = name_or_id.strip()
        low = needle.lower()
        for item in self._items.values():
            if item.get("status", "live") != "live":
                continue
            if item["id"] == low or item["name"].lower() == low:
                return item
        part = [i for i in self._items.values() if low in i["name"].lower()]
        if len(part) == 1:
            return part[0]
        return None

    def update_item(self, item_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Apply edits to a live item and stamp the update date."""
        item = self._items.get(item_id)
        if item is None or item.get("status", "live") != "live":
            raise DrawerError(f"No live item keyed '{item_id}'.")
        merged = {
            "name": fields.get("name", item["name"]),
            "kind": fields.get("kind", item["kind"]),
            "room": fields.get("room", item["room"]),
            "container": fields.get("container", item["container"]),
            "description": fields.get("description", item["description"]),
            "tags": fields.get("tags", item["tags"]),
            "photo_hint": fields.get("photo_hint", item["photo_hint"]),
        }
        item.update(self._validate(merged))
        item["updated"] = today()
        self.save()
        return item

    # ------------------------------------------------------------ moves
    def mark_moved(
        self,
        item_id: str,
        new_room: str,
        new_container: str = "",
        note: str = "",
        when: str | None = None,
    ) -> dict[str, Any]:
        """Record that an item was physically relocated."""
        item = self._items.get(item_id)
        if item is None or item.get("status", "live") != "live":
            raise DrawerError(f"No live item keyed '{item_id}'.")
        if not str(new_room).strip():
            raise DrawerError(
                "Tell me the new room - or use the same room with a new "
                "container if it just changed shelves."
            )
        move = {
            "date": parse_date(when),
            "from_room": item["room"],
            "from_container": item["container"],
            "to_room": str(new_room).strip(),
            "to_container": str(new_container).strip(),
            "note": str(note).strip(),
        }
        item["moves"].append(move)
        item["room"] = move["to_room"]
        item["container"] = move["to_container"]
        item["updated"] = today()
        self.save()
        return item

    def move_history(self, item_id: str) -> list[dict[str, Any]]:
        item = self._items.get(item_id)
        if item is None:
            raise DrawerError(f"No item keyed '{item_id}'.")
        return item["moves"]

    # ----------------------------------------------------------- removal
    def remove_item(
        self, item_id: str, reason: str = "", gone_to: str = ""
    ) -> dict[str, Any]:
        """Mark an item gone (used up, given away, thrown out)."""
        item = self._items.get(item_id)
        if item is None or item.get("status", "live") != "live":
            raise DrawerError(f"No live item keyed '{item_id}'.")
        item["status"] = "gone"
        item["updated"] = today()
        item["moves"].append(
            {
                "date": today(),
                "from_room": item["room"],
                "from_container": item["container"],
                "to_room": "gone",
                "to_container": str(gone_to).strip(),
                "note": str(reason).strip() or "removed",
            }
        )
        self.save()
        return item

    # -------------------------------------------------------------- rooms
    def rooms(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.live_items():
            counts[item["room"]] = counts.get(item["room"], 0) + 1
        return dict(sorted(counts.items()))
