import json
import re
from typing import List
from anthropic import Anthropic
from scripts.models import Paper, ScoredPaper

SCORING_SYSTEM_PROMPT = """You are an expert AI researcher evaluating academic papers for relevance and quality.
You MUST respond with valid JSON only. No markdown, no extra text."""

SCORING_USER_TEMPLATE = """Evaluate this paper for the "{category_name}" category (type: {category_type}).

Title: {title}
Authors: {authors}
Abstract: {abstract}
HuggingFace upvotes: {hf_upvotes}{venue_line}
{scoring_note}
Score this paper 1-10 on each dimension:
1. topic_importance: Is the problem worth solving? Not trivial or marginal?
2. trend_alignment: Does it align with current frontiers in {category_name}?
3. community_attention: Based on upvotes and topic appeal (use HF upvotes as signal if >0)
4. practical_significance: Does it have concrete practical value, not just theoretical?
5. author_prestige: Are authors from well-known institutions (MIT, CMU, Google, DeepMind, Stanford, etc.)?
6. paper_completeness: Does it appear to have solid experiments and rigorous methodology?

Weights: topic_importance=25%, trend_alignment=20%, community_attention=15%, practical_significance=20%, author_prestige=10%, paper_completeness=10%

Respond ONLY with this JSON (use single quotes inside strings if you need quotes):
{{
  "score": <weighted_average_float>,
  "breakdown": {{
    "topic_importance": <1-10>,
    "trend_alignment": <1-10>,
    "community_attention": <1-10>,
    "practical_significance": <1-10>,
    "author_prestige": <1-10>,
    "paper_completeness": <1-10>
  }},
  "rationale": "<one sentence overall assessment>",
  "pros": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "cons": ["<weakness 1>", "<weakness 2>"]
}}"""


def build_scoring_prompt(paper: Paper, category_name: str, category_type: str, scoring_note: str = "") -> str:
    venue_line = f"\nVenue: {paper.venue}" if paper.venue else ""
    note_block = f"Note: {scoring_note}" if scoring_note else ""
    return SCORING_USER_TEMPLATE.format(
        category_name=category_name,
        category_type=category_type,
        title=paper.title,
        authors=", ".join(paper.authors[:5]) or "Unknown",
        abstract=paper.abstract[:800],
        hf_upvotes=paper.hf_upvotes,
        venue_line=venue_line,
        scoring_note=note_block,
    )


def parse_score_response(response_text: str, paper: Paper) -> ScoredPaper:
    """Parse Claude's JSON response into a ScoredPaper."""
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not json_match:
        return ScoredPaper(paper=paper, score=5.0, score_breakdown={}, rationale="Parse error")

    data = json.loads(json_match.group())
    return ScoredPaper(
        paper=paper,
        score=float(data.get("score", 5.0)),
        score_breakdown=data.get("breakdown", {}),
        rationale=data.get("rationale", ""),
        pros=data.get("pros", []),
        cons=data.get("cons", []),
    )


def _venue_bonus(paper: Paper) -> float:
    """Bonus/penalty based on conference acceptance and community signal.

    Conference papers are strongly preferred. Non-conference papers only pass
    through if they have meaningful community attention (high HF upvotes).
    """
    if paper.source == "conference" or paper.venue:
        return 1.5
    # Non-conference: gate on HF trending signal
    if paper.hf_upvotes >= 20:
        return 1.0
    if paper.hf_upvotes >= 10:
        return 0.3
    # Plain arXiv with no conference signal and low community attention
    return -1.5


def score_paper(
    paper: Paper,
    category_name: str,
    category_type: str,
    client: Anthropic,
    scoring_note: str = "",
) -> ScoredPaper:
    """Score a single paper using Claude Haiku."""
    prompt = build_scoring_prompt(paper, category_name, category_type, scoring_note)
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=768,
            system=SCORING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        sp = parse_score_response(message.content[0].text, paper)
        sp.score = min(10.0, max(1.0, sp.score + _venue_bonus(paper)))
        return sp
    except Exception as e:
        base = min(10.0, max(1.0, 5.0 + _venue_bonus(paper)))
        return ScoredPaper(paper=paper, score=base, score_breakdown={}, rationale=f"Error: {e}")


def select_top_papers(
    papers: List[Paper],
    category_name: str,
    category_type: str,
    n: int,
    client: Anthropic,
    scoring_note: str = "",
) -> List[ScoredPaper]:
    """Score all papers and return top n by score."""
    scored = [score_paper(p, category_name, category_type, client, scoring_note) for p in papers]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:n]
