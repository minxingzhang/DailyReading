import json
from unittest.mock import MagicMock
from datetime import datetime
from scripts.generate_analysis import build_analysis_prompt, parse_analysis_response
from scripts.models import Paper, ScoredPaper, PaperAnalysis


def _make_scored_paper():
    paper = Paper(
        arxiv_id="2401.00001",
        title="Jailbreak LLMs via Adversarial Prompts",
        authors=["Alice Smith (MIT)", "Bob Jones (CMU)"],
        abstract="We propose AdvPrompt, a method to systematically jailbreak large language models.",
        url="https://arxiv.org/abs/2401.00001",
        published=datetime(2026, 3, 3),
        hf_upvotes=150,
    )
    return ScoredPaper(paper=paper, score=8.5, score_breakdown={}, rationale="Timely and impactful.")


def test_build_analysis_prompt_contains_required_fields():
    sp = _make_scored_paper()
    prompt = build_analysis_prompt(sp)
    assert sp.paper.title in prompt
    assert "tldr" in prompt.lower() or "TL;DR" in prompt
    assert "research_question" in prompt.lower() or "Research Question" in prompt
    assert "prior_work" in prompt.lower() or "Prior Work" in prompt
    assert "solution" in prompt.lower()
    assert "discussion" in prompt.lower()


def test_parse_analysis_response_extracts_all_fields():
    sample = {
        "tldr_zh": "本文提出了一种对抗提示方法来越狱大型语言模型。",
        "tldr_en": "This paper proposes AdvPrompt to systematically jailbreak LLMs.",
        "research_question_zh": "如何系统地评估LLM在对抗提示下的安全性？",
        "research_question_en": "How to systematically evaluate LLM safety against adversarial prompts?",
        "prior_work_zh": "现有方法依赖手动设计的越狱提示，缺乏系统性。",
        "prior_work_en": "Existing methods rely on manually crafted jailbreak prompts lacking systematicity.",
        "solution_zh": "提出AdvPrompt框架，自动搜索对抗性提示模板。",
        "solution_en": "Proposes AdvPrompt framework for automated adversarial prompt template search.",
        "results_zh": "在GPT-4等7个模型上攻击成功率提升30%。",
        "results_en": "30% improvement in attack success rate across 7 models including GPT-4.",
        "discussion_zh": ["LLM对齐机制的根本性局限", "防御方法的军备竞赛问题"],
        "discussion_en": ["Fundamental limitations of LLM alignment", "Arms race problem in defense methods"]
    }
    sp = _make_scored_paper()
    analysis = parse_analysis_response(json.dumps(sample), sp)
    assert analysis.tldr_zh == "本文提出了一种对抗提示方法来越狱大型语言模型。"
    assert analysis.tldr_en == "This paper proposes AdvPrompt to systematically jailbreak LLMs."
    assert len(analysis.discussion_zh) == 2
    assert len(analysis.discussion_en) == 2
    assert isinstance(analysis, PaperAnalysis)
