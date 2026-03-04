import json
import os
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Any, Optional

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _get_env() -> Environment:
    return Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def render_daily_page(
    date: str,
    categories_data: List[Dict[str, Any]],
    base_url: str,
    site_title: str,
) -> str:
    env = _get_env()
    tmpl = env.get_template("daily.html.j2")
    total = sum(len(c["analyses"]) for c in categories_data)
    return tmpl.render(
        date=date,
        categories=categories_data,
        base_url=base_url,
        site_title=site_title,
        total_papers=total,
    )


def render_index_page(
    archive_data: List[Dict[str, Any]],
    latest_date: Optional[str],
    base_url: str,
) -> str:
    env = _get_env()
    tmpl = env.get_template("index.html.j2")
    return tmpl.render(
        archive_data=archive_data,
        latest_date=latest_date,
        base_url=base_url,
    )


def render_email_html(
    date: str,
    categories_data: List[Dict[str, Any]],
    full_url: str,
) -> str:
    env = _get_env()
    tmpl = env.get_template("email.html.j2")
    return tmpl.render(date=date, categories=categories_data, full_url=full_url)


def write_daily_page(date: str, html: str, docs_dir: str) -> str:
    """Write the daily page to docs/<date>/index.html. Returns the path."""
    output_dir = os.path.join(docs_dir, date)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def write_meta_json(date: str, categories_data: List[Dict[str, Any]], docs_dir: str) -> None:
    """Write a lightweight meta.json for the index accordion."""
    meta = {
        "date": date,
        "categories": [
            {
                "id": cat["id"],
                "name_zh": cat["name_zh"],
                "name_en": cat["name_en"],
                "papers": [
                    {
                        "title": a.scored_paper.paper.title,
                        "tldr_zh": a.tldr_zh,
                        "url": a.scored_paper.paper.url,
                        "venue": a.scored_paper.paper.venue,
                        "published": a.scored_paper.paper.published.strftime("%Y-%m-%d"),
                    }
                    for a in cat["analyses"]
                ],
            }
            for cat in categories_data
        ],
    }
    output_dir = os.path.join(docs_dir, date)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))


def load_archive_data(docs_dir: str) -> List[Dict[str, Any]]:
    """Load meta.json files from all date directories, newest first."""
    archive = []
    if not os.path.isdir(docs_dir):
        return archive
    for d in sorted(os.listdir(docs_dir), reverse=True):
        if len(d) != 10 or d[4] != "-":  # YYYY-MM-DD only
            continue
        meta_path = os.path.join(docs_dir, d, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                archive.append(json.load(f))
    return archive


def write_index_page(html: str, docs_dir: str) -> str:
    """Write the homepage to docs/index.html."""
    path = os.path.join(docs_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
