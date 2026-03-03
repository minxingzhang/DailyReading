import os
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Any

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


def render_index_page(archive_dates: List[str], latest_date: str, base_url: str) -> str:
    env = _get_env()
    tmpl = env.get_template("index.html.j2")
    return tmpl.render(
        archive_dates=archive_dates,
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


def write_index_page(html: str, docs_dir: str) -> str:
    """Write the homepage to docs/index.html."""
    path = os.path.join(docs_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
