"""Search tests: the 'do we have an HDMI adapter?' path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from junk_drawer.search import matches, search, tokenize


@pytest.fixture
def sample_search_items() -> list[dict]:
    raw = (Path(__file__).parent / "fixtures" / "sample_drawer.json").read_text(
        encoding="utf-8"
    )
    return list(json.loads(raw)["items"].values())


class TestTokenize:
    def test_strips_question_words(self) -> None:
        assert tokenize("Do we have an HDMI adapter?") == ["hdmi", "adapter"]

    def test_keeps_plugs_and_hyphens(self) -> None:
        assert "usb-c" in tokenize("short USB-C cable")


class TestRanking:
    def test_finds_by_tags(self, sample_search_items: list[dict]) -> None:
        results = search(sample_search_items, "hdmi adapter")
        assert results
        assert results[0]["id"] == "hdmi-to-mini-hdmi-adapter"

    def test_finds_plural_free(self, sample_search_items: list[dict]) -> None:
        results = search(sample_search_items, "AA batteries")
        assert [r["id"] for r in results] == ["aa-battery-full-box"]

    def test_requires_every_token(self, sample_search_items: list[dict]) -> None:
        assert search(sample_search_items, "hdmi batteries") == []

    def test_no_loose_match_for_unknown_word(self, sample_search_items) -> None:
        assert search(sample_search_items, "spanner") == []
        results = search(sample_search_items, "craft thread")
        assert [r["id"] for r in results] == ["craft-thread-red"]

    def test_gone_items_ignored(self, sample_search_items: list[dict]) -> None:
        results = search(sample_search_items, "micro usb red")
        assert all(r["id"] != "micro-usb-cable-red" for r in results)

    def test_empty_query(self, sample_search_items: list[dict]) -> None:
        assert search(sample_search_items, "  ?  ") == []

    def test_matches_scorer_directly(self) -> None:
        item = {"id": "x", "name": "HDMI adapter", "kind": "adapter",
                "tags": ["hdmi"], "container": "", "room": "office",
                "description": "", "status": "live", "moves": []}
        ok, score = matches(item, ["hdmi", "adapter"])
        assert ok and score > 0
        ok_no, _ = matches(item, ["ribbon"])
        assert not ok_no


class TestHelper:
    def test_sample_fixture_shape(self, sample_search_items: list[dict]) -> None:
        ids = [i["id"] for i in sample_search_items]
        assert "spare-house-key" in ids
        statuses = {i.get("status", "live") for i in sample_search_items}
        assert "gone" in statuses  # the gone item rides along as a filter test
