"""
Deduplication module for DailyPaper.

Storage format: data/seen_papers.json
Structure: {"arxiv_id": "YYYY-MM-DD", ...}

Design rationale:
- Dict keys give O(1) membership lookup in Python
- Date value enables audit trail (when was this paper first pushed)
- Compact JSON (no indent/newlines) for space efficiency
- Grows ~300 bytes/day; after 5 years ≈ 500 KB — trivial to load
- Load once per pipeline run; all per-paper checks are in-memory O(1)
"""

import json
import os
from typing import Dict, List

from scripts.models import Paper

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "seen_papers.json"
)


def load_seen_ids(filepath: str = _DEFAULT_PATH) -> Dict[str, str]:
    """Load {arxiv_id: date_first_seen} from JSON. Returns {} if file absent."""
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen_ids(seen: Dict[str, str], filepath: str = _DEFAULT_PATH) -> None:
    """Persist seen IDs to compact JSON (no whitespace for space efficiency)."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, separators=(",", ":"))


def filter_new_papers(papers: List[Paper], seen: Dict[str, str]) -> List[Paper]:
    """Return only papers whose arxiv_id has not been seen before."""
    return [p for p in papers if p.arxiv_id and p.arxiv_id not in seen]


def mark_papers_as_seen(
    papers: List[Paper], seen: Dict[str, str], date: str
) -> Dict[str, str]:
    """
    Return updated seen dict with paper IDs added.
    Never overwrites an existing date (preserves the original push date).
    """
    updated = dict(seen)
    for p in papers:
        if p.arxiv_id and p.arxiv_id not in updated:
            updated[p.arxiv_id] = date
    return updated
