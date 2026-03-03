from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from scripts.fetch_papers import fetch_arxiv_papers, fetch_hf_papers, merge_and_deduplicate
from scripts.models import Paper


def _make_mock_arxiv_result(arxiv_id, title, authors, abstract, published):
    r = MagicMock()
    r.get_short_id.return_value = arxiv_id
    r.title = title
    r.authors = [MagicMock() for _ in authors]
    for i, name in enumerate(authors):
        r.authors[i].name = name
    r.summary = abstract
    r.entry_id = f"http://arxiv.org/abs/{arxiv_id}v1"
    r.published = published
    return r


def test_fetch_arxiv_papers_returns_papers(mocker):
    mock_result = _make_mock_arxiv_result(
        "2401.00001", "Test LLM Security Paper",
        ["Alice Smith", "Bob Jones"],
        "We study jailbreak attacks on LLMs.",
        datetime(2026, 3, 3, tzinfo=timezone.utc)
    )
    mocker.patch("arxiv.Search")
    mock_client_instance = MagicMock()
    mock_client_instance.results.return_value = iter([mock_result])
    mocker.patch("arxiv.Client", return_value=mock_client_instance)

    papers = fetch_arxiv_papers(
        keywords=["jailbreak"],
        arxiv_categories=["cs.CR"],
        lookback_hours=48
    )

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.00001"
    assert papers[0].title == "Test LLM Security Paper"
    assert papers[0].source == "arxiv"


def test_merge_and_deduplicate_removes_duplicates():
    p1 = Paper(arxiv_id="111", title="A", authors=[], abstract="", url="", published=datetime.now())
    p2 = Paper(arxiv_id="111", title="A", authors=[], abstract="", url="", published=datetime.now(), hf_upvotes=10)
    p3 = Paper(arxiv_id="222", title="B", authors=[], abstract="", url="", published=datetime.now())

    merged = merge_and_deduplicate([[p1, p3], [p2]])
    assert len(merged) == 2
    ids = {p.arxiv_id for p in merged}
    assert ids == {"111", "222"}


def test_merge_keeps_paper_with_hf_upvotes():
    p_arxiv = Paper(arxiv_id="111", title="A", authors=[], abstract="", url="", published=datetime.now(), hf_upvotes=0)
    p_hf = Paper(arxiv_id="111", title="A", authors=[], abstract="", url="", published=datetime.now(), hf_upvotes=42, source="hf")

    merged = merge_and_deduplicate([[p_arxiv], [p_hf]])
    assert len(merged) == 1
    assert merged[0].hf_upvotes == 42
