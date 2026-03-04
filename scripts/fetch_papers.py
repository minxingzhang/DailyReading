import re
import arxiv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import List
from scripts.models import Paper

# Top conferences across AI / Security / Robotics
_TOP_CONFERENCES = [
    "NeurIPS", "ICML", "ICLR", "CVPR", "ICCV", "ECCV", "AAAI", "IJCAI",
    "ACL", "EMNLP", "NAACL", "COLING",
    "CCS", "USENIX Security", "IEEE S&P", "NDSS", "RAID", "AsiaCCS",
    "ICRA", "IROS", "CoRL", "RSS",
    "KDD", "WWW", "SIGMOD", "VLDB",
]

_VENUE_RE = re.compile(
    r'(?:accepted|to appear|published|appearing|presented)\s+(?:at|in|@)\s+'
    r'([A-Za-z][A-Za-z\s&\-]+?(?:\s+20\d\d)?)\b',
    re.IGNORECASE,
)


def _extract_venue(comment: str, journal_ref: str) -> str:
    """Try to detect a top-conference venue from arXiv comment / journal_ref."""
    text = f"{comment or ''} {journal_ref or ''}"
    m = _VENUE_RE.search(text)
    if m:
        candidate = m.group(1).strip().rstrip(".,")
        # Only return if it matches a known conference name
        candidate_upper = candidate.upper()
        for conf in _TOP_CONFERENCES:
            if conf.upper() in candidate_upper:
                return candidate
        # Return anyway if the pattern fired (e.g. "ECCV 2024")
        if len(candidate) <= 30:
            return candidate
    # Fallback: scan for bare conference names
    for conf in _TOP_CONFERENCES:
        if re.search(r'\b' + re.escape(conf) + r'\b', text, re.IGNORECASE):
            return conf
    return ""


def fetch_arxiv_papers(
    keywords: List[str],
    arxiv_categories: List[str],
    lookback_hours: int = 48,
) -> List[Paper]:
    """Fetch papers from arXiv matching any keyword in given categories."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    kw_query = " OR ".join(f'"{kw}"' for kw in keywords)
    cat_query = " OR ".join(f"cat:{c}" for c in arxiv_categories)
    query = f"({kw_query}) AND ({cat_query})"

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=100,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    for result in client.results(search):
        if result.published < cutoff:
            break
        venue = _extract_venue(
            getattr(result, "comment", "") or "",
            getattr(result, "journal_ref", "") or "",
        )
        papers.append(Paper(
            arxiv_id=result.get_short_id(),
            title=result.title,
            authors=[a.name for a in result.authors],
            abstract=result.summary.replace("\n", " "),
            url=result.entry_id,
            published=result.published,
            hf_upvotes=0,
            source="arxiv",
            venue=venue,
        ))

    return papers


def fetch_hf_papers() -> List[Paper]:
    """Fetch today's papers from HuggingFace Daily Papers with upvote counts."""
    url = "https://huggingface.co/papers"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DailyPaper/1.0)"}

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    papers = []

    for article in soup.select("article"):
        title_el = article.select_one("h3 a, h2 a")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")

        arxiv_id = None
        if "/papers/" in href:
            arxiv_id = href.split("/papers/")[-1].strip("/")

        upvote_el = article.select_one("[data-upvotes], .upvote-count, button[aria-label*='upvote']")
        hf_upvotes = 0
        if upvote_el:
            try:
                hf_upvotes = int(upvote_el.get_text(strip=True))
            except (ValueError, AttributeError):
                pass

        abstract_el = article.select_one("p")
        abstract = abstract_el.get_text(strip=True) if abstract_el else ""

        papers.append(Paper(
            arxiv_id=arxiv_id,
            title=title,
            authors=[],
            abstract=abstract,
            url=f"https://huggingface.co{href}" if href.startswith("/") else href,
            published=datetime.now(timezone.utc),
            hf_upvotes=hf_upvotes,
            source="hf",
            venue="",
        ))

    return papers


def merge_and_deduplicate(papers_lists: List[List[Paper]]) -> List[Paper]:
    """Merge multiple paper lists; deduplicate by arxiv_id, preferring HF version (has upvotes)."""
    seen: dict = {}

    for papers in papers_lists:
        for paper in papers:
            if paper.arxiv_id is None:
                continue
            if paper.arxiv_id not in seen:
                seen[paper.arxiv_id] = paper
            else:
                existing = seen[paper.arxiv_id]
                if paper.hf_upvotes > existing.hf_upvotes:
                    if not paper.abstract and existing.abstract:
                        paper.abstract = existing.abstract
                    # Preserve venue from arXiv version
                    if not paper.venue and existing.venue:
                        paper.venue = existing.venue
                    seen[paper.arxiv_id] = paper

    return list(seen.values())
