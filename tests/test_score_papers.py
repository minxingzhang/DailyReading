from unittest.mock import MagicMock
from datetime import datetime
from scripts.score_papers import build_scoring_prompt, parse_score_response, select_top_papers
from scripts.models import Paper, ScoredPaper


def _make_paper(arxiv_id, title, abstract, hf_upvotes=0):
    return Paper(
        arxiv_id=arxiv_id, title=title, authors=["Alice"],
        abstract=abstract, url="", published=datetime.now(),
        hf_upvotes=hf_upvotes
    )


def test_build_scoring_prompt_contains_title_and_abstract():
    paper = _make_paper("111", "Jailbreak Attack on LLMs", "We study adversarial prompts.")
    prompt = build_scoring_prompt(paper, category_name="LLM Security", category_type="worthwhile")
    assert "Jailbreak Attack on LLMs" in prompt
    assert "adversarial prompts" in prompt
    assert "LLM Security" in prompt


def test_parse_score_response_extracts_score():
    response_text = '''
    {
      "score": 7.5,
      "breakdown": {
        "topic_importance": 8,
        "trend_alignment": 7,
        "community_attention": 6,
        "practical_significance": 8,
        "author_prestige": 7,
        "paper_completeness": 8
      },
      "rationale": "This paper addresses a timely and important problem in LLM security."
    }
    '''
    scored = parse_score_response(response_text, paper=_make_paper("111", "Test", "Abstract"))
    assert scored.score == 7.5
    assert scored.rationale == "This paper addresses a timely and important problem in LLM security."


def test_select_top_papers_returns_n_best(mocker):
    papers = [
        _make_paper("001", "Paper A", "Abstract A"),
        _make_paper("002", "Paper B", "Abstract B"),
        _make_paper("003", "Paper C", "Abstract C"),
        _make_paper("004", "Paper D", "Abstract D"),
    ]

    scores = {"001": 5.0, "002": 9.0, "003": 7.0, "004": 8.5}
    mock_client = MagicMock()

    def mock_score(paper, category_name, category_type, client):
        return ScoredPaper(paper=paper, score=scores[paper.arxiv_id], score_breakdown={}, rationale="")

    mocker.patch("scripts.score_papers.score_paper", side_effect=mock_score)

    top = select_top_papers(papers, "LLM Security", "worthwhile", n=3, client=mock_client)
    assert len(top) == 3
    assert top[0].paper.arxiv_id == "002"  # score 9.0
    assert top[1].paper.arxiv_id == "004"  # score 8.5
    assert top[2].paper.arxiv_id == "003"  # score 7.0
