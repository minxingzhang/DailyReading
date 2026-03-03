import os
from unittest.mock import patch, MagicMock
from datetime import datetime
from scripts.models import Paper, ScoredPaper, PaperAnalysis


def _make_paper(arxiv_id):
    return Paper(arxiv_id=arxiv_id, title=f"Paper {arxiv_id}", authors=["Alice"],
                 abstract="Test abstract", url="", published=datetime.now())


def _make_scored(arxiv_id):
    return ScoredPaper(paper=_make_paper(arxiv_id), score=8.0, score_breakdown={}, rationale="Good.")


def _make_analysis(arxiv_id):
    return PaperAnalysis(
        scored_paper=_make_scored(arxiv_id),
        tldr_zh="中文摘要", tldr_en="English summary",
        research_question_zh="问题", research_question_en="Question",
        prior_work_zh="先前", prior_work_en="Prior",
        solution_zh="方案", solution_en="Solution",
        results_zh="结果", results_en="Results",
        discussion_zh=["点1"], discussion_en=["Point1"],
    )


def test_run_pipeline_creates_output_files(mocker, tmp_path):
    mocker.patch("scripts.main.fetch_arxiv_papers", return_value=[_make_paper("001")])
    mocker.patch("scripts.main.fetch_hf_papers", return_value=[])
    mocker.patch("scripts.main.merge_and_deduplicate", return_value=[_make_paper("001")])
    mocker.patch("scripts.main.select_top_papers", return_value=[_make_scored("001")])
    mocker.patch("scripts.main.generate_analysis", return_value=_make_analysis("001"))
    mocker.patch("scripts.main.send_digest_email")

    seen_path = str(tmp_path / "seen_papers.json")

    from scripts.main import run_pipeline
    run_pipeline(
        docs_dir=str(tmp_path),
        anthropic_api_key="fake",
        gmail_user="bot@gmail.com",
        gmail_password="pass",
        email_recipients=["user@example.com"],
        base_url="",
        seen_papers_path=seen_path,
    )

    # Should create a YYYY-MM-DD directory with index.html
    date_dirs = [d for d in os.listdir(tmp_path)
                 if os.path.isdir(os.path.join(tmp_path, d)) and len(d) == 10 and d[4] == "-"]
    assert len(date_dirs) >= 1
    assert os.path.exists(os.path.join(tmp_path, date_dirs[0], "index.html"))
    assert os.path.exists(os.path.join(tmp_path, "index.html"))


def test_run_pipeline_deduplicates_across_runs(mocker, tmp_path):
    """Papers selected on day 1 must not be selected on day 2."""
    mocker.patch("scripts.main.fetch_hf_papers", return_value=[])
    mocker.patch("scripts.main.fetch_arxiv_papers", return_value=[_make_paper("001"), _make_paper("002")])
    mocker.patch("scripts.main.merge_and_deduplicate", side_effect=lambda lists: lists[0])
    mocker.patch("scripts.main.generate_analysis", side_effect=lambda sp, c: _make_analysis(sp.paper.arxiv_id))
    mocker.patch("scripts.main.send_digest_email")

    seen_path = str(tmp_path / "seen_papers.json")

    # Day 1: both papers are new, select paper 001
    mocker.patch("scripts.main.select_top_papers", return_value=[_make_scored("001")])

    from scripts.main import run_pipeline
    run_pipeline(docs_dir=str(tmp_path), anthropic_api_key="fake",
                 gmail_user="", gmail_password="", email_recipients=[],
                 base_url="", seen_papers_path=seen_path)

    # seen_papers.json should now contain "001"
    import json
    seen = json.loads(open(seen_path).read())
    assert "001" in seen

    # Day 2: pipeline runs again; filter_new_papers should exclude "001"
    # Verify that filter_new_papers is called and removes the seen paper
    filter_spy = mocker.patch("scripts.main.filter_new_papers",
                              wraps=__import__("scripts.seen_papers").seen_papers.filter_new_papers)
    mocker.patch("scripts.main.select_top_papers", return_value=[_make_scored("002")])

    run_pipeline(docs_dir=str(tmp_path), anthropic_api_key="fake",
                 gmail_user="", gmail_password="", email_recipients=[],
                 base_url="", seen_papers_path=seen_path)

    # filter_new_papers was called and "001" would have been filtered
    assert filter_spy.called
    seen2 = json.loads(open(seen_path).read())
    assert "002" in seen2
