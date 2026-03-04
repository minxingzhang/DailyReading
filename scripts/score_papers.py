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
3. community_attention: BONUS-ONLY signal. Default is 5 (neutral) when upvotes are low or unknown. Only score ABOVE 5 if HF upvotes are high (>=10) or the topic is clearly trending. NEVER score below 5 — lack of community attention is not a weakness.
4. practical_significance: Does it have concrete practical value, not just theoretical?
5. author_prestige: BONUS-ONLY signal. Default is 5 (neutral) for unknown or less prominent institutions. Only score ABOVE 5 if authors are from well-known institutions (MIT, CMU, Google, DeepMind, Stanford, etc.). NEVER score below 5 — unknown affiliation is not a weakness.
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
  "pros": ["<strength 1 in English>", "<strength 2 in English>", "<strength 3 in English>"],
  "pros_zh": ["<优势1（中文）>", "<优势2（中文）>", "<优势3（中文）>"],
  "cons": ["<weakness 1 in English>", "<weakness 2 in English>"],
  "cons_zh": ["<不足1（中文）>", "<不足2（中文）>"]
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
        pros_zh=data.get("pros_zh", []),
        cons_zh=data.get("cons_zh", []),
    )


def _venue_bonus(paper: Paper, current_year: int = 2026) -> float:
    """Bonus/penalty based on conference acceptance and community signal.

    Conference papers are strongly preferred, with newer years scoring higher.
    Non-conference papers only pass through if they have strong community attention.
    """
    if paper.source == "conference" or paper.venue:
        pub_year = paper.published.year if paper.published else current_year
        if pub_year >= current_year:
            return 2.0   # current year: highest priority
        elif pub_year >= current_year - 1:
            return 1.7   # 1 year ago
        else:
            return 1.5   # 2 years ago (oldest in window)
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
    current_year: int = 2026,
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
        sp.score = min(10.0, max(1.0, sp.score + _venue_bonus(paper, current_year)))
        return sp
    except Exception as e:
        base = min(10.0, max(1.0, 5.0 + _venue_bonus(paper, current_year)))
        return ScoredPaper(paper=paper, score=base, score_breakdown={}, rationale=f"Error: {e}")


def select_top_papers(
    papers: List[Paper],
    category_name: str,
    category_type: str,
    n: int,
    client: Anthropic,
    scoring_note: str = "",
    current_year: int = 2026,
    min_score: float = 6.0,
) -> List[ScoredPaper]:
    """Score all papers and return top n by score, excluding low-quality papers."""
    scored = [
        score_paper(p, category_name, category_type, client, scoring_note, current_year)
        for p in papers
    ]
    scored.sort(key=lambda x: x.score, reverse=True)
    # 宁缺勿滥: only publish papers that meet the quality bar
    qualified = [sp for sp in scored if sp.score >= min_score]
    if qualified:
        return qualified[:n]
    # Fallback: no paper met the threshold.
    # Return up to 3 highest-scoring papers within this category (scoring already reflects
    # topic-layer priorities via scoring_note, so top scores = highest-priority topics).
    return scored[:3]
