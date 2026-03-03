from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Paper:
    arxiv_id: Optional[str]
    title: str
    authors: List[str]
    abstract: str
    url: str
    published: datetime
    hf_upvotes: int = 0
    source: str = "arxiv"  # "arxiv" or "hf"


@dataclass
class ScoredPaper:
    paper: Paper
    score: float
    score_breakdown: dict
    rationale: str


@dataclass
class PaperAnalysis:
    scored_paper: ScoredPaper
    tldr_zh: str
    tldr_en: str
    research_question_zh: str
    research_question_en: str
    prior_work_zh: str
    prior_work_en: str
    solution_zh: str
    solution_en: str
    results_zh: str
    results_en: str
    discussion_zh: List[str]
    discussion_en: List[str]
