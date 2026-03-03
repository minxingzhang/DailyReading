import os
import tempfile
from datetime import datetime
from scripts.render_html import render_daily_page, render_index_page, write_daily_page, write_index_page
from scripts.models import Paper, ScoredPaper, PaperAnalysis


def _make_analysis(arxiv_id="001", title="Test Paper"):
    paper = Paper(arxiv_id=arxiv_id, title=title, authors=["Alice"], abstract="",
                  url="https://arxiv.org/abs/001", published=datetime.now(), hf_upvotes=10)
    scored = ScoredPaper(paper=paper, score=8.0, score_breakdown={}, rationale="Good paper.")
    return PaperAnalysis(
        scored_paper=scored,
        tldr_zh="这是一篇关于测试的论文。", tldr_en="This is a test paper.",
        research_question_zh="问题", research_question_en="Question",
        prior_work_zh="先前工作", prior_work_en="Prior work",
        solution_zh="解决方案", solution_en="Solution",
        results_zh="结果", results_en="Results",
        discussion_zh=["讨论点1"], discussion_en=["Discussion point 1"],
    )


def test_render_daily_page_contains_paper_title():
    categories_data = [
        {"id": "llm_security", "name_zh": "LLM 安全", "name_en": "LLM Security",
         "analyses": [_make_analysis("001", "LLM Jailbreak Attack")]},
    ]
    html = render_daily_page("2026-03-03", categories_data, base_url="", site_title="DailyPaper")
    assert "LLM Jailbreak Attack" in html
    assert "LLM 安全" in html
    assert "这是一篇关于测试的论文" in html


def test_render_index_page_contains_archive_dates():
    html = render_index_page(["2026-03-03", "2026-03-02"], latest_date="2026-03-03", base_url="")
    assert "2026-03-03" in html
    assert "2026-03-02" in html


def test_write_daily_page_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = write_daily_page("2026-03-03", "<html>test</html>", tmp)
        assert os.path.exists(path)
        assert open(path).read() == "<html>test</html>"


def test_write_index_page_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = write_index_page("<html>index</html>", tmp)
        assert os.path.exists(path)
        assert open(path).read() == "<html>index</html>"
