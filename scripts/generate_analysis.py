import json
import re
from anthropic import Anthropic
from scripts.models import ScoredPaper, PaperAnalysis

ANALYSIS_SYSTEM = """You are an expert AI researcher writing concise bilingual paper summaries for busy researchers.
Each summary must be readable in under 5 minutes. Be concrete and specific.
Respond ONLY with valid JSON."""

ANALYSIS_USER_TEMPLATE = """Write a concise bilingual analysis of this paper. Each section: 2-4 sentences max.

Paper: {title}
Authors: {authors}
Abstract: {abstract}
Score rationale: {rationale}

Respond ONLY with this JSON (all fields required):
{{
  "tldr_zh": "<ONE sentence in Chinese: core contribution>",
  "tldr_en": "<ONE sentence in English: core contribution>",
  "research_question_zh": "<2-3 sentences: what problem and why it matters>",
  "research_question_en": "<2-3 sentences: what problem and why it matters>",
  "prior_work_zh": "<2-3 sentences: 1-2 key limitations of existing approaches>",
  "prior_work_en": "<2-3 sentences: 1-2 key limitations of existing approaches>",
  "solution_zh": "<3-4 sentences: core method/framework and main contributions>",
  "solution_en": "<3-4 sentences: core method/framework and main contributions>",
  "results_zh": "<2-3 sentences: key findings, include numbers if available>",
  "results_en": "<2-3 sentences: key findings, include numbers if available>",
  "discussion_zh": ["<point 1>", "<point 2>", "<point 3>"],
  "discussion_en": ["<point 1>", "<point 2>", "<point 3>"]
}}

Total Chinese text <= 600 characters. Total English text <= 800 words."""


def build_analysis_prompt(scored_paper: ScoredPaper) -> str:
    p = scored_paper.paper
    return ANALYSIS_USER_TEMPLATE.format(
        title=p.title,
        authors=", ".join(p.authors[:5]) or "Unknown",
        abstract=p.abstract[:1000],
        rationale=scored_paper.rationale,
    )


def parse_analysis_response(response_text: str, scored_paper: ScoredPaper) -> PaperAnalysis:
    """Parse Claude's JSON response into a PaperAnalysis."""
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON found in response: {response_text[:200]}")

    data = json.loads(json_match.group())
    return PaperAnalysis(
        scored_paper=scored_paper,
        tldr_zh=data["tldr_zh"],
        tldr_en=data["tldr_en"],
        research_question_zh=data["research_question_zh"],
        research_question_en=data["research_question_en"],
        prior_work_zh=data["prior_work_zh"],
        prior_work_en=data["prior_work_en"],
        solution_zh=data["solution_zh"],
        solution_en=data["solution_en"],
        results_zh=data["results_zh"],
        results_en=data["results_en"],
        discussion_zh=data["discussion_zh"],
        discussion_en=data["discussion_en"],
    )


def generate_analysis(scored_paper: ScoredPaper, client: Anthropic) -> PaperAnalysis:
    """Generate bilingual structured analysis using Claude Sonnet."""
    prompt = build_analysis_prompt(scored_paper)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_analysis_response(message.content[0].text, scored_paper)
