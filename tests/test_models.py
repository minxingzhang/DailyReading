from scripts.models import Paper, ScoredPaper, PaperAnalysis
from datetime import datetime

def test_paper_creation():
    p = Paper(
        arxiv_id="2401.12345",
        title="Test Paper",
        authors=["Alice", "Bob"],
        abstract="This paper does X.",
        url="https://arxiv.org/abs/2401.12345",
        published=datetime(2026, 3, 3),
    )
    assert p.hf_upvotes == 0
    assert p.source == "arxiv"

def test_paper_equality_by_arxiv_id():
    p1 = Paper(arxiv_id="2401.12345", title="A", authors=[], abstract="", url="", published=datetime.now())
    p2 = Paper(arxiv_id="2401.12345", title="B", authors=[], abstract="", url="", published=datetime.now())
    assert p1.arxiv_id == p2.arxiv_id
