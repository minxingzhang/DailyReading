import re
from anthropic import Anthropic
from scripts.models import ScoredPaper, PaperAnalysis

ANALYSIS_SYSTEM = """You are an expert AI researcher writing concise bilingual paper summaries for busy researchers.
Each summary must be readable in under 5 minutes. Be concrete and specific."""

ANALYSIS_USER_TEMPLATE = """Write a concise bilingual analysis of this paper. Each section: 2-4 sentences max.

Paper: {title}
Authors: {authors}
Abstract: {abstract}
Score rationale: {rationale}

Guidelines:
- Chinese sections: <= 600 characters total
- English sections: <= 800 words total
- discussion_zh and discussion_en: exactly 3 items each
- Be specific and concrete, avoid vague phrases"""

# Tool schema forces valid structured output — no JSON parsing needed
ANALYSIS_TOOL = {
    "name": "output_analysis",
    "description": "Output structured bilingual paper analysis",
    "input_schema": {
        "type": "object",
        "properties": {
            "tldr_zh": {"type": "string", "description": "ONE sentence in Chinese: core contribution"},
            "tldr_en": {"type": "string", "description": "ONE sentence in English: core contribution"},
            "significance_zh": {"type": "string", "description": "2-3 sentences in Chinese: why this paper matters — its importance and potential impact for the research community or practitioners"},
            "significance_en": {"type": "string", "description": "2-3 sentences in English: why this paper matters — its importance and potential impact for the research community or practitioners"},
            "research_question_zh": {"type": "string", "description": "2-3 sentences: what problem and why it matters (Chinese)"},
            "research_question_en": {"type": "string", "description": "2-3 sentences: what problem and why it matters (English)"},
            "prior_work_zh": {"type": "string", "description": "2-3 sentences: key limitations of existing approaches (Chinese)"},
            "prior_work_en": {"type": "string", "description": "2-3 sentences: key limitations of existing approaches (English)"},
            "solution_zh": {"type": "string", "description": "3-4 sentences: core method and main contributions (Chinese)"},
            "solution_en": {"type": "string", "description": "3-4 sentences: core method and main contributions (English)"},
            "results_zh": {"type": "string", "description": "2-3 sentences: key findings with numbers if available (Chinese)"},
            "results_en": {"type": "string", "description": "2-3 sentences: key findings with numbers if available (English)"},
            "discussion_zh": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 3 discussion points in Chinese",
            },
            "discussion_en": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 3 discussion points in English",
            },
        },
        "required": [
            "tldr_zh", "tldr_en",
            "significance_zh", "significance_en",
            "research_question_zh", "research_question_en",
            "prior_work_zh", "prior_work_en",
            "solution_zh", "solution_en",
            "results_zh", "results_en",
            "discussion_zh", "discussion_en",
        ],
    },
}


def build_analysis_prompt(scored_paper: ScoredPaper) -> str:
    p = scored_paper.paper
    return ANALYSIS_USER_TEMPLATE.format(
        title=p.title,
        authors=", ".join(p.authors[:5]) or "Unknown",
        abstract=p.abstract[:1000],
        rationale=scored_paper.rationale,
    )


def generate_analysis(scored_paper: ScoredPaper, client: Anthropic) -> PaperAnalysis:
    """Generate bilingual structured analysis using Claude Sonnet with tool_use for reliable output."""
    prompt = build_analysis_prompt(scored_paper)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=ANALYSIS_SYSTEM,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "output_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "tool_use":
            d = block.input
            return PaperAnalysis(
                scored_paper=scored_paper,
                tldr_zh=d["tldr_zh"],
                tldr_en=d["tldr_en"],
                significance_zh=d["significance_zh"],
                significance_en=d["significance_en"],
                research_question_zh=d["research_question_zh"],
                research_question_en=d["research_question_en"],
                prior_work_zh=d["prior_work_zh"],
                prior_work_en=d["prior_work_en"],
                solution_zh=d["solution_zh"],
                solution_en=d["solution_en"],
                results_zh=d["results_zh"],
                results_en=d["results_en"],
                discussion_zh=d["discussion_zh"],
                discussion_en=d["discussion_en"],
            )
    raise ValueError("No tool_use block found in Anthropic response")
