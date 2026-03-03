import json
import os
import tempfile
from datetime import datetime
from scripts.seen_papers import load_seen_ids, save_seen_ids, filter_new_papers, mark_papers_as_seen
from scripts.models import Paper


def _paper(arxiv_id):
    return Paper(arxiv_id=arxiv_id, title=f"P{arxiv_id}", authors=[], abstract="",
                 url="", published=datetime.now())


def test_load_seen_ids_returns_empty_dict_when_file_missing():
    with tempfile.TemporaryDirectory() as tmp:
        result = load_seen_ids(os.path.join(tmp, "nonexistent.json"))
    assert result == {}


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "seen.json")
        data = {"2401.001": "2026-03-03", "2401.002": "2026-03-04"}
        save_seen_ids(data, path)
        loaded = load_seen_ids(path)
    assert loaded == data


def test_save_uses_compact_json():
    """File should use no indentation for efficient storage."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "seen.json")
        save_seen_ids({"2401.001": "2026-03-03"}, path)
        raw = open(path).read()
    assert "\n" not in raw  # no newlines = compact


def test_filter_new_papers_removes_seen():
    seen = {"111": "2026-03-01", "222": "2026-03-02"}
    papers = [_paper("111"), _paper("333"), _paper("222"), _paper("444")]
    new = filter_new_papers(papers, seen)
    assert [p.arxiv_id for p in new] == ["333", "444"]


def test_filter_new_papers_keeps_all_when_seen_empty():
    papers = [_paper("aaa"), _paper("bbb")]
    assert filter_new_papers(papers, {}) == papers


def test_mark_papers_as_seen_adds_new_ids():
    seen = {"existing": "2026-03-01"}
    papers = [_paper("new1"), _paper("new2")]
    updated = mark_papers_as_seen(papers, seen, "2026-03-03")
    assert updated["new1"] == "2026-03-03"
    assert updated["new2"] == "2026-03-03"
    assert updated["existing"] == "2026-03-01"  # unchanged


def test_mark_papers_does_not_overwrite_earlier_date():
    seen = {"111": "2026-03-01"}
    papers = [_paper("111")]  # same paper again
    updated = mark_papers_as_seen(papers, seen, "2026-03-10")
    assert updated["111"] == "2026-03-01"  # original date preserved


def test_filter_then_mark_workflow():
    """Full dedup workflow: filter → process → mark → save → reload → filter again."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "seen.json")
        day1_papers = [_paper("A"), _paper("B"), _paper("C")]

        seen = load_seen_ids(path)
        new_day1 = filter_new_papers(day1_papers, seen)
        assert len(new_day1) == 3

        seen = mark_papers_as_seen(new_day1, seen, "2026-03-03")
        save_seen_ids(seen, path)

        # Day 2: A and B are repeats, D is new
        day2_papers = [_paper("A"), _paper("B"), _paper("D")]
        seen2 = load_seen_ids(path)
        new_day2 = filter_new_papers(day2_papers, seen2)
        assert [p.arxiv_id for p in new_day2] == ["D"]
