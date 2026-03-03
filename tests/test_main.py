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

    from scripts.main import run_pipeline
    run_pipeline(
        docs_dir=str(tmp_path),
        anthropic_api_key="fake",
        gmail_user="bot@gmail.com",
        gmail_password="pass",
        email_recipients=["user@example.com"],
        base_url="",
    )

    # Should create at least one date directory with index.html
    subdirs = [d for d in os.listdir(tmp_path) if os.path.isdir(os.path.join(tmp_path, d))]
    assert len(subdirs) >= 1
    date_dir = subdirs[0]
    assert os.path.exists(os.path.join(tmp_path, date_dir, "index.html"))
    # Should create docs/index.html
    assert os.path.exists(os.path.join(tmp_path, "index.html"))
