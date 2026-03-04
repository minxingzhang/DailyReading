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


def fetch_semantic_scholar_papers(
    query: str,
    top_conferences: List[str],
    min_year: int = 2024,
    max_results: int = 50,
) -> List[Paper]:
    """Fetch conference-accepted papers from Semantic Scholar API."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "fields": "title,abstract,authors,year,venue,externalIds,publicationDate",
        "limit": min(max_results, 100),
    }
    headers = {"User-Agent": "DailyPaper/1.0 (academic research)"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [S2] API error: {e}")
        return []

    conf_upper = [c.upper() for c in top_conferences]
    papers = []

    for item in data.get("data", []):
        venue = (item.get("venue") or "").strip()
        year = item.get("year") or 0

        if year < min_year:
            continue

        # Match venue against top conferences
        venue_matched = ""
        if venue:
            venue_u = venue.upper()
            for conf, conf_u in zip(top_conferences, conf_upper):
                if conf_u in venue_u or venue_u in conf_u:
                    venue_matched = venue
                    break

        if not venue_matched:
            continue

        ext_ids = item.get("externalIds") or {}
        arxiv_id = ext_ids.get("ArXiv")
        s2_id = item.get("paperId", "")
        unique_id = arxiv_id if arxiv_id else f"s2:{s2_id}"

        paper_url = (
            f"https://arxiv.org/abs/{arxiv_id}"
            if arxiv_id
            else f"https://www.semanticscholar.org/paper/{s2_id}"
        )

        pub_str = item.get("publicationDate") or ""
        try:
            published = datetime.strptime(pub_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            published = datetime(max(year, 2020), 1, 1, tzinfo=timezone.utc)

        title = (item.get("title") or "").strip()
        abstract = (item.get("abstract") or "").replace("\n", " ").strip()
        authors = [a.get("name", "") for a in (item.get("authors") or [])]

        if not title or not abstract:
            continue

        papers.append(Paper(
            arxiv_id=unique_id,
            title=title,
            authors=authors,
            abstract=abstract,
            url=paper_url,
            published=published,
            hf_upvotes=0,
            source="conference",
            venue=venue_matched,
        ))

    return papers


def merge_and_deduplicate(papers_lists: List[List[Paper]]) -> List[Paper]:
    """Merge multiple paper lists; deduplicate by arxiv_id.

    Priority: conference source > HF upvotes > first-seen.
    Venue and conference designation are preserved across merges.
    """
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
                    # Preserve venue and conference source from whichever has it
                    if not paper.venue and existing.venue:
                        paper.venue = existing.venue
                    if existing.source == "conference":
                        paper.source = "conference"
                    seen[paper.arxiv_id] = paper
                elif existing.source != "conference" and paper.source == "conference":
                    # Conference version wins even with same upvotes
                    paper.hf_upvotes = existing.hf_upvotes  # preserve any upvotes
                    seen[paper.arxiv_id] = paper

    return list(seen.values())
